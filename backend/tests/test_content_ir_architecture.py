"""Content IR architecture integration tests.

Covers validator, writer, compile, download, and Agent policy.
"""
import json
import os
import sys
import tempfile
from pathlib import Path
from unittest import mock

import app.main  # noqa: F401 - import side effect registers module capabilities
import pytest

# Add repo root to allow importing modules
_repo_root = Path(__file__).resolve().parents[2]
if str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))

from app.core.exceptions import ConflictError
from app.core.exceptions import ValidationError as AppValidationError
from app.services.content.ir_validator import validate_ir, validate_ir_sync
from app.services.content.ir_writer import write_ir

# ── Helpers ──────────────────────────────────────────────────────────


def _valid_document_ir(**overrides) -> dict:
    ir = {
        "schema_version": "1.0",
        "content_type": "document",
        "title": "Test Document",
        "blocks": [
            {"type": "heading", "text": "Title", "level": 1},
            {"type": "paragraph", "text": "Body text"},
            {"type": "table", "data": {"headers": ["A", "B"], "rows": [["1", "2"]]}},
        ],
    }
    ir.update(overrides)
    return ir


def _valid_spreadsheet_ir(**overrides) -> dict:
    ir = {
        "schema_version": "1.0",
        "content_type": "spreadsheet",
        "title": "Test Sheet",
        "blocks": [
            {
                "type": "sheet",
                "text": "Sheet1",
                "children": [
                    {
                        "type": "table",
                        "data": {
                            "start_cell": "A1",
                            "headers": ["日期", "产品"],
                            "rows": [["2026-07-01", "A"]],
                        },
                    }
                ],
            }
        ],
    }
    ir.update(overrides)
    return ir


def _valid_presentation_ir(**overrides) -> dict:
    ir = {
        "schema_version": "1.0",
        "content_type": "presentation",
        "title": "Test Deck",
        "blocks": [
            {
                "type": "slide",
                "children": [
                    {"type": "heading", "text": "Slide 1", "level": 1},
                    {"type": "paragraph", "text": "Content"},
                ],
            }
        ],
    }
    ir.update(overrides)
    return ir


async def _delete_content_packages(db, package_ids: list[int]) -> None:
    from app.models.content import ContentPackage, ContentPackageVersion, ResourceRef
    from sqlalchemy import delete

    if not package_ids:
        return
    await db.execute(delete(ResourceRef).where(ResourceRef.package_id.in_(package_ids)))
    await db.execute(delete(ContentPackageVersion).where(ContentPackageVersion.package_id.in_(package_ids)))
    await db.execute(delete(ContentPackage).where(ContentPackage.id.in_(package_ids)))
    await db.commit()


# ====================================================================
# 1. Content IR validator tests
# ====================================================================


class TestValidateIR:
    """Tests for content IR validation."""

    @pytest.mark.asyncio
    async def test_valid_document_validates_ok(self):
        result = await validate_ir(_valid_document_ir())
        assert result.valid is True
        assert len(result.errors) == 0

    @pytest.mark.asyncio
    async def test_missing_required_fields(self):
        result = await validate_ir({})
        assert result.valid is False
        codes = {e.code for e in result.errors}
        assert "missing_required_field" in codes
        paths = {e.path for e in result.errors}
        assert "schema_version" in paths
        assert "content_type" in paths
        assert "title" in paths
        assert "blocks" in paths

    @pytest.mark.asyncio
    async def test_invalid_content_type(self):
        ir = _valid_document_ir(content_type="unknown_type")
        result = await validate_ir(ir)
        assert result.valid is False
        assert any(e.code == "invalid_content_type" for e in result.errors)

    @pytest.mark.asyncio
    async def test_unsupported_block_type(self):
        ir = _valid_document_ir(blocks=[{"type": "textboxx", "text": "bad"}])
        result = await validate_ir(ir)
        assert result.valid is False
        assert any(e.code == "unsupported_block_type" for e in result.errors)

    @pytest.mark.asyncio
    async def test_spreadsheet_top_level_non_sheet(self):
        ir = _valid_spreadsheet_ir(blocks=[{"type": "paragraph", "text": "wrong"}])
        result = await validate_ir(ir)
        assert result.valid is False
        assert any(e.code == "spreadsheet_needs_sheet" for e in result.errors)

    @pytest.mark.asyncio
    async def test_spreadsheet_table_row_length_mismatch(self):
        ir = {
            "schema_version": "1.0",
            "content_type": "spreadsheet",
            "title": "Bad Sheet",
            "blocks": [
                {
                    "type": "sheet",
                    "text": "Sheet1",
                    "children": [
                        {
                            "type": "table",
                            "data": {
                                "headers": ["A", "B", "C"],
                                "rows": [["1", "2"]],
                            },
                        }
                    ],
                }
            ],
        }
        result = await validate_ir(ir)
        assert result.valid is False
        assert any(e.code == "row_length_mismatch" for e in result.errors)

    @pytest.mark.asyncio
    async def test_presentation_top_level_non_slide(self):
        ir = _valid_presentation_ir(blocks=[{"type": "paragraph", "text": "wrong"}])
        result = await validate_ir(ir)
        assert result.valid is False
        assert any(e.code == "presentation_needs_slide" for e in result.errors)

    @pytest.mark.asyncio
    async def test_presentation_slide_allowed_children(self):
        ir = {
            "schema_version": "1.0",
            "content_type": "presentation",
            "title": "Bad Deck",
            "blocks": [
                {
                    "type": "slide",
                    "children": [{"type": "sheet", "text": "not allowed inside slide"}],
                }
            ],
        }
        result = await validate_ir(ir)
        assert result.valid is False
        assert any(e.code == "unsupported_block_in_slide" for e in result.errors)

    @pytest.mark.asyncio
    async def test_mixed_resource_ref_unresolved(self):
        ir = {
            "schema_version": "1.0",
            "content_type": "mixed",
            "title": "Mixed Doc",
            "blocks": [
                {"type": "paragraph", "text": "text", "resource_ref": "r_nonexistent"}
            ],
            "resources": [{"id": "r1", "resource_type": "image"}],
        }
        result = await validate_ir(ir)
        assert result.valid is False
        assert any(e.code == "unresolved_resource_ref" for e in result.errors)

    @pytest.mark.asyncio
    async def test_memory_block_with_style(self):
        ir = {
            "schema_version": "1.0",
            "content_type": "memory",
            "title": "Memory",
            "blocks": [{"type": "paragraph", "text": "fact", "style": {"bold": True}}],
        }
        result = await validate_ir(ir)
        assert result.valid is False
        assert any(e.code == "memory_no_style" for e in result.errors)

    @pytest.mark.asyncio
    async def test_image_at_least_one_block_or_resource(self):
        ir = {
            "schema_version": "1.0",
            "content_type": "image",
            "title": "Image",
            "blocks": [],
            "resources": [],
        }
        result = await validate_ir(ir)
        assert result.valid is False
        assert any(e.code == "image_no_content" for e in result.errors)

    @pytest.mark.asyncio
    async def test_spreadsheet_invalid_excel_address(self):
        ir = {
            "schema_version": "1.0",
            "content_type": "spreadsheet",
            "title": "Bad Sheet",
            "blocks": [
                {
                    "type": "sheet",
                    "children": [
                        {"type": "range", "data": {"start_cell": "INVALID", "end_cell": "B10"}}
                    ],
                }
            ],
        }
        result = await validate_ir(ir)
        assert result.valid is False
        assert any(e.code == "invalid_excel_address" for e in result.errors)

    def test_validate_ir_sync(self):
        """Synchronous wrapper works."""
        result = validate_ir_sync(_valid_document_ir())
        assert result.valid is True

    def test_validate_ir_sync_invalid(self):
        result = validate_ir_sync({"content_type": "bad"})
        assert result.valid is False


# ====================================================================
# 2. Content IR writer tests
# ====================================================================


class TestWriteIR:
    """Tests for content IR writer. Mocks DB and cross-module calls."""

    @pytest.mark.asyncio
    async def test_invalid_ir_raises_structured_error(self):
        """Invalid IR raises AppValidationError with structured details."""
        from app.database import AsyncSessionLocal
        async with AsyncSessionLocal() as db:
            with pytest.raises(AppValidationError) as exc_info:
                await write_ir(
                    db,
                    {"schema_version": "1.0", "content_type": "document", "title": "bad", "blocks": [{"type": "textboxx", "text": "bad"}]},
                    owner_id=1,
                    caller="user:1",
                )
            assert exc_info.value.details is not None
            assert len(exc_info.value.details) > 0
            assert any(d.get("code") == "unsupported_block_type" for d in exc_info.value.details)

    @pytest.mark.asyncio
    async def test_document_write_creates_package(self):
        """Valid document IR creates ContentPackage + version."""
        from app.database import AsyncSessionLocal
        from app.models.content import ContentPackage, ContentPackageVersion

        owner_id = 9991
        async with AsyncSessionLocal() as db:
            try:
                result = await write_ir(
                    db, _valid_document_ir(),
                    owner_id=owner_id,
                    caller=f"user:{owner_id}",
                )
                assert result["canonical_source"] == "content_package"
                assert result["owner_id"] == owner_id
                assert result["package_id"] > 0
                assert result["version_id"] > 0
                assert result["version_no"] >= 1

                # Verify DB records
                pkg = await db.get(ContentPackage, result["package_id"])
                assert pkg is not None
                assert pkg.owner_id == owner_id
                assert pkg.package_type == "document"

                ver = await db.get(ContentPackageVersion, result["version_id"])
                assert ver is not None
                assert ver.package_id == pkg.id

                # Cleanup
                await _delete_content_packages(db, [result["package_id"]])
            except Exception:
                await db.rollback()
                raise

    @pytest.mark.asyncio
    async def test_consecutive_writes_different_packages(self):
        """Two writes without source_file_id create different packages."""
        from app.database import AsyncSessionLocal

        owner_id = 9992
        async with AsyncSessionLocal() as db:
            try:
                r1 = await write_ir(
                    db, _valid_document_ir(title="Doc A"),
                    owner_id=owner_id, caller=f"user:{owner_id}",
                )
                r2 = await write_ir(
                    db, _valid_document_ir(title="Doc B"),
                    owner_id=owner_id, caller=f"user:{owner_id}",
                )
                assert r1["package_id"] != r2["package_id"]

                # Cleanup
                await _delete_content_packages(db, [r1["package_id"], r2["package_id"]])
            except Exception:
                await db.rollback()
                raise

    @pytest.mark.asyncio
    async def test_spreadsheet_write_passes_headers_to_excel(self):
        """Spreadsheet write should include headers + rows in update_range call."""
        ir = _valid_spreadsheet_ir()
        owner_id = 9993

        with mock.patch("app.services.content.ir_writer.call_capability") as mock_cc:
            mock_cc.return_value = {"state_key": "test_wb_1"}

            from app.database import AsyncSessionLocal
            async with AsyncSessionLocal() as db:
                try:
                    result = await write_ir(
                        db, ir,
                        owner_id=owner_id,
                        caller=f"user:{owner_id}",
                    )
                    assert result["canonical_source"] == "excel_engine"
                    # Verify update_range was called with headers + rows
                    update_calls = [
                        c for c in mock_cc.call_args_list
                        if c[0][1] == "update_range"
                    ]
                    assert len(update_calls) > 0
                    args = update_calls[-1][0]
                    # args[0]=module, args[1]=action, args[2]=params, args[3]=caller
                    params = args[2]
                    assert params["rows"] == [["日期", "产品"], ["2026-07-01", "A"]]
                    assert params["start_row"] == 0
                    assert params["start_col"] == 0
                except Exception:
                    await db.rollback()
                    raise

    @pytest.mark.asyncio
    async def test_spreadsheet_write_parses_start_cell(self):
        """start_cell=A5: C5 should become start_row=4, start_col=2."""
        ir = _valid_spreadsheet_ir()
        ir["blocks"][0]["children"][0]["data"]["start_cell"] = "C5"

        with mock.patch("app.services.content.ir_writer.call_capability") as mock_cc:
            mock_cc.return_value = {"state_key": "test_wb_2"}
            from app.database import AsyncSessionLocal
            async with AsyncSessionLocal() as db:
                try:
                    await write_ir(
                        db, ir, owner_id=9994, caller="user:9994",
                    )
                    update_calls = [
                        c for c in mock_cc.call_args_list
                        if c[0][1] == "update_range"
                    ]
                    assert len(update_calls) > 0
                    args = update_calls[-1][0]
                    params = args[2]
                    assert params["start_row"] == 4  # 0-based, row 5
                    assert params["start_col"] == 2  # 0-based, col C
                except Exception:
                    await db.rollback()
                    raise

    @pytest.mark.asyncio
    async def test_image_write_returns_resource_ids(self):
        """Image write should return non-empty resource_ids list."""
        ir = {
            "schema_version": "1.0",
            "content_type": "image",
            "title": "Test Image",
            "blocks": [{"type": "image", "text": "desc", "resource_ref": "r1"}],
            "resources": [{"id": "r1", "resource_type": "image", "data_b64": "AAAA"}],
        }
        from app.database import AsyncSessionLocal

        with mock.patch("app.services.content.ir_writer.call_capability") as mock_cc:
            mock_cc.return_value = {"id": 100, "state_key": "test"}
            async with AsyncSessionLocal() as db:
                result = await write_ir(
                    db, ir, owner_id=9995, caller="user:9995",
                )
                assert result["canonical_source"] == "resource"
                # store_resource should have been called at least once
                store_calls = [
                    c for c in mock_cc.call_args_list
                    if c[0][1] == "store_resource"
                ]
                assert len(store_calls) >= 1

    @pytest.mark.asyncio
    async def test_version_conflict_detected(self):
        """expected_version_id mismatch should raise ConflictError."""
        from app.database import AsyncSessionLocal

        owner_id = 9996
        async with AsyncSessionLocal() as db:
            try:
                r1 = await write_ir(
                    db, _valid_document_ir(),
                    owner_id=owner_id, caller=f"user:{owner_id}",
                )
                wrong_version = (r1["version_id"] or 0) + 99999
                with pytest.raises(ConflictError):
                    await write_ir(
                        db, _valid_document_ir(),
                        owner_id=owner_id,
                        caller=f"user:{owner_id}",
                        source_file_id=r1.get("source_file_id"),
                        expected_version_id=wrong_version,
                    )
                # Cleanup
                await _delete_content_packages(db, [r1["package_id"]])
            except Exception:
                await db.rollback()
                raise


# ====================================================================
# 3. Compile / download tests
# ====================================================================


class TestCompileDownload:
    """Tests for content compile and download."""

    @pytest.mark.asyncio
    async def test_content_compile_no_file_record(self):
        """content:compile should NOT create framework_file_items."""
        from app.database import AsyncSessionLocal
        from app.models.file import File
        from app.routers.content import _cap_compile
        from sqlalchemy import func, select

        owner_id = 9997
        tmp_fd, tmp_path = tempfile.mkstemp(suffix=".docx")
        os.close(tmp_fd)
        Path(tmp_path).write_bytes(b"compiled")
        async with AsyncSessionLocal() as db:
            result = await write_ir(
                db,
                _valid_document_ir(title="Compile Test"),
                owner_id=owner_id,
                caller=f"user:{owner_id}",
            )
            package_id = result["package_id"]
            before = (await db.execute(select(func.count()).select_from(File))).scalar_one()

        try:
            with mock.patch(
                "app.services.content.export_service.ContentExportService._compile_to_file"
            ) as mock_compile:
                mock_compile.return_value = (Path(tmp_path), "test.docx")
                compiled = await _cap_compile(
                    {"package_id": package_id, "target_format": "docx"},
                    f"user:{owner_id}",
                )
            assert compiled["success"] is True
            assert compiled["data"]["filename"] == "test.docx"

            async with AsyncSessionLocal() as db:
                after = (await db.execute(select(func.count()).select_from(File))).scalar_one()
                assert after == before
        finally:
            async with AsyncSessionLocal() as db:
                await _delete_content_packages(db, [package_id])
            Path(tmp_path).unlink(missing_ok=True)

    @pytest.mark.asyncio
    async def test_compile_path_security_rejects_invalid_path(self):
        """Compile with invalid temp path should fail security."""
        from app.database import AsyncSessionLocal
        from app.routers.content import _cap_compile

        owner_id = 9998
        invalid_path = Path(__file__).resolve()
        async with AsyncSessionLocal() as db:
            result = await write_ir(
                db,
                _valid_document_ir(title="Invalid Path Compile Test"),
                owner_id=owner_id,
                caller=f"user:{owner_id}",
            )
            package_id = result["package_id"]

        try:
            with mock.patch(
                "app.services.content.export_service.ContentExportService._compile_to_file"
            ) as mock_compile:
                mock_compile.return_value = (invalid_path, "test.docx")
                compiled = await _cap_compile(
                    {"package_id": package_id, "target_format": "docx"},
                    f"user:{owner_id}",
                )
            assert compiled == {"success": False, "error": "Invalid compile output path"}
        finally:
            async with AsyncSessionLocal() as db:
                await _delete_content_packages(db, [package_id])

    @pytest.mark.asyncio
    async def test_compile_rejects_filename_with_path_sep(self):
        """Filenames with / or \\ should be rejected."""
        from app.database import AsyncSessionLocal
        from app.routers.content import _cap_compile

        owner_id = 9999
        tmp_fd, tmp_path = tempfile.mkstemp(suffix=".docx")
        os.close(tmp_fd)
        Path(tmp_path).write_bytes(b"compiled")
        async with AsyncSessionLocal() as db:
            result = await write_ir(
                db,
                _valid_document_ir(title="Bad Filename Compile Test"),
                owner_id=owner_id,
                caller=f"user:{owner_id}",
            )
            package_id = result["package_id"]

        try:
            with mock.patch(
                "app.services.content.export_service.ContentExportService._compile_to_file"
            ) as mock_compile:
                mock_compile.return_value = (Path(tmp_path), "../bad.docx")
                compiled = await _cap_compile(
                    {"package_id": package_id, "target_format": "docx"},
                    f"user:{owner_id}",
                )
            assert compiled == {"success": False, "error": "Invalid filename"}
        finally:
            async with AsyncSessionLocal() as db:
                await _delete_content_packages(db, [package_id])
            Path(tmp_path).unlink(missing_ok=True)

    @pytest.mark.asyncio
    async def test_excel_compile_nonexistent_workbook_fails(self):
        """excel-engine:compile_xlsx with missing state_key should fail."""
        from app.services.module_registry import call_capability

        result = await call_capability(
            "excel-engine", "compile_xlsx",
            {"state_key": "__test_nonexistent_workbook__"},
            caller="user:4",
            caller_role="viewer",
        )
        data = result.get("data", result) if isinstance(result, dict) else {}
        assert data.get("success") is False
        assert "Workbook not found" in data.get("error", "")

    @pytest.mark.asyncio
    async def test_spreadsheet_package_skipped_in_compile(self):
        """Spreadsheet ContentPackages should be skipped in download compile."""
        from app.database import AsyncSessionLocal
        from app.models.content import ContentPackage, ContentPackageVersion
        from app.models.file import File
        from app.routers.file_transfer import _try_compile_from_content_package

        owner_id = 4
        async with AsyncSessionLocal() as db:
            file_rec = File(
                name="spreadsheet-source",
                extension="xlsx",
                size=0,
                owner_id=owner_id,
                storage_path="missing.xlsx",
                mime_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                deleted=False,
            )
            db.add(file_rec)
            await db.flush()
            pkg = ContentPackage(
                owner_id=owner_id,
                source_file_id=file_rec.id,
                package_type="spreadsheet",
                origin_type="generated",
                source_extension="xlsx",
                status="parsed",
            )
            db.add(pkg)
            await db.flush()
            version = ContentPackageVersion(
                package_id=pkg.id,
                version_no=1,
                content_json=json.dumps({"manifest": {}, "blocks": []}),
                operation_type="write_ir",
                created_by=owner_id,
            )
            db.add(version)
            await db.flush()
            pkg.current_version_id = version.id
            await db.commit()
            file_id = file_rec.id
            package_id = pkg.id

        try:
            with mock.patch("app.routers.file_transfer.call_capability") as mock_call:
                async with AsyncSessionLocal() as db:
                    result = await _try_compile_from_content_package(db, file_id, owner_id)
            assert result is None
            mock_call.assert_not_called()
        finally:
            async with AsyncSessionLocal() as cleanup_db:
                await _delete_content_packages(cleanup_db, [package_id])
                file_to_delete = await cleanup_db.get(File, file_id)
                if file_to_delete:
                    await cleanup_db.delete(file_to_delete)
                    await cleanup_db.commit()


# ====================================================================
# 4. Agent policy tests
# ====================================================================


class TestAgentPolicy:
    """Tests for Agent action policy enforcement."""

    @pytest.mark.asyncio
    async def test_system_caller_validate_ir_allowed(self):
        """system:agent-engine can call validate_ir (viewer-level, no owner needed)."""
        from app.services.module_registry import call_capability

        result = await call_capability(
            "content", "validate_ir",
            {"content_ir": _valid_document_ir()},
            caller="system:agent-engine",
            caller_role="viewer",
        )
        if isinstance(result, dict):
            inner = result.get("data", result)
            if isinstance(inner, dict):
                error = inner.get("error", result.get("error", ""))
                if error:
                    assert "permission" not in error.lower()
                    assert "denied" not in error.lower()

    @pytest.mark.asyncio
    async def test_system_caller_write_ir_rejected(self):
        """system:agent-engine cannot call write_ir (needs real user)."""
        from app.services.module_registry import call_capability

        result = await call_capability(
            "content", "write_ir",
            {"content_ir": _valid_document_ir()},
            caller="system:agent-engine",
            caller_role="editor",
        )
        if isinstance(result, dict):
            error = result.get("error", "")
            data = result.get("data", {}) if isinstance(result.get("data"), dict) else {}
            err_msg = error or data.get("error", "")
            # Must fail
            if not err_msg:
                # If it didn't fail, at least validate that success is False
                success = result.get("success", data.get("success", True))
                assert success is not True, "system principal must not be able to write"

    @pytest.mark.asyncio
    async def test_system_principal_returns_zero(self):
        """system:* principal returns 0 (no user context)."""
        from app.services.file_reader import is_system_caller, resolve_caller_user_id

        uid = resolve_caller_user_id("system:agent-engine")
        assert uid == 0
        assert is_system_caller("system:agent-engine") is True
        assert is_system_caller("user:4") is False

    @pytest.mark.asyncio
    async def test_system_hard_blocked_actions(self):
        """Verify all expected actions are in SYSTEM_HARD_BLOCKED_ACTIONS."""
        from modules.agent.backend.services.action_policy import (
            SENSITIVE_ACTION_PATTERNS,
            SYSTEM_HARD_BLOCKED_ACTIONS,
        )

        expected = {
            "office-gen__docx",
            "office-gen__xlsx",
            "office-gen__pptx",
            "office-gen__pdf",
            "office-gen__replace_existing",
            "office-gen__generate_to_artifact",
            "office-gen__export_to_artifact",
            "office-gen__convert",
            "desktop-tools__write_file",
            "desktop-tools__replace_file",
            "desktop-tools__create_file",
            "desktop-tools__publish_artifact",
            "desktop-tools__replace_file_from_artifact",
        }
        for action in expected:
            assert action in SYSTEM_HARD_BLOCKED_ACTIONS, f"{action} should be hard blocked"

        # Also verify they are in SENSITIVE_ACTION_PATTERNS
        for action in expected:
            module = action.split("__")[0]
            assert any(
                module in p or action == p
                for p in SENSITIVE_ACTION_PATTERNS
            ), f"{action} should be in sensitive patterns"

    @pytest.mark.asyncio
    async def test_check_action_allowed_hard_blocks_system(self):
        """check_action_allowed(user_id=0) should hard block sensitive actions."""
        from app.database import AsyncSessionLocal

        from modules.agent.backend.services.action_policy import (
            SYSTEM_HARD_BLOCKED_ACTIONS,
            check_action_allowed,
        )

        sample_action = next(iter(SYSTEM_HARD_BLOCKED_ACTIONS))
        async with AsyncSessionLocal() as db:
            result = await check_action_allowed(
                db, sample_action, "test_agent", user_id=0,
            )
        assert result.get("allowed") is False
        assert result.get("action") == "block"

    @pytest.mark.asyncio
    async def test_normal_user_not_blocked_for_same_action(self):
        """Normal user (user_id>0) gets policy-based decision, not hard block."""
        from app.database import AsyncSessionLocal

        from modules.agent.backend.services.action_policy import (
            SYSTEM_HARD_BLOCKED_ACTIONS,
            check_action_allowed,
        )

        sample_action = next(iter(SYSTEM_HARD_BLOCKED_ACTIONS))
        async with AsyncSessionLocal() as db:
            result = await check_action_allowed(
                db, sample_action, "test_agent", user_id=4,
            )
        # Normal user should get a policy decision (could be blocked or confirm)
        # but NOT the hard block message
        if not result.get("allowed"):
            reason = result.get("reason", "")
            assert "hard blocked for system principal" not in reason

    @pytest.mark.asyncio
    async def test_system_caller_can_validate_ir_via_api(self):
        """system:agent-engine can call validate_ir through module_registry."""
        from app.services.module_registry import call_capability

        result = await call_capability(
            "content", "validate_ir",
            {"content_ir": _valid_document_ir()},
            caller="system:agent-engine",
            caller_role="viewer",
        )
        # Must not raise permission error; may succeed or fail on content
        if isinstance(result, dict):
            err = result.get("error", "")
            assert "permission" not in err.lower()


# ====================================================================
# 5. Correction loop constants
# ====================================================================


class TestCorrectionLoopConstants:
    """Test the correction loop limits and prompt template."""

    def test_max_retries_is_3(self):
        from modules.agent.backend.services.content_ir_correction import MAX_RETRIES

        assert MAX_RETRIES == 3

    def test_correction_prompt_contains_errors_placeholder(self):
        from modules.agent.backend.services.content_ir_correction import CORRECTION_PROMPT

        assert "{validation_errors}" in CORRECTION_PROMPT


# ====================================================================
# 6. Capability registration tests
# ====================================================================


class TestCapabilityRegistration:
    """Content IR capabilities must be registered with correct min_role."""

    def test_content_capabilities_listed(self):
        from app.services.module_registry import list_capabilities
        caps = list_capabilities()
        content_caps = {c["action"]: c["min_role"] for c in caps if c["module"] == "content"}

        assert content_caps.get("validate_ir") == "viewer"
        assert content_caps.get("normalize_ir") == "viewer"
        assert content_caps.get("write_ir") == "editor"
        assert content_caps.get("compile") == "viewer"
        assert content_caps.get("store_analysis_resource") == "viewer"

    def test_excel_capabilities_listed(self):
        from app.services.module_registry import list_capabilities
        caps = list_capabilities()
        excel_caps = {c["action"]: c["min_role"] for c in caps if c["module"] == "excel-engine"}

        assert excel_caps.get("compile_xlsx") == "viewer"
        assert excel_caps.get("export_xlsx") == "editor"

    def test_image_vision_capability_listed(self):
        from app.services.module_registry import list_capabilities
        caps = list_capabilities()
        iv_caps = {c["action"]: c["min_role"] for c in caps if c["module"] == "image-vision"}
        assert iv_caps.get("describe") == "viewer"
