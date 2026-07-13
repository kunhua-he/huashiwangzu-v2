from __future__ import annotations

import sys
import types
import uuid
from types import SimpleNamespace

import pytest
import pytest_asyncio
from app.database import AsyncSessionLocal
from sqlalchemy import delete, select

from .models import MemoryExperience

if "huashiwangzu_modules" not in sys.modules:
    namespace = types.ModuleType("huashiwangzu_modules")
    namespace.__path__ = []
    sys.modules["huashiwangzu_modules"] = namespace
if "huashiwangzu_modules.memory" not in sys.modules:
    memory_namespace = types.ModuleType("huashiwangzu_modules.memory")
    memory_namespace.__path__ = []
    sys.modules["huashiwangzu_modules.memory"] = memory_namespace
sys.modules["huashiwangzu_modules.memory.models"] = sys.modules[MemoryExperience.__module__]

from .services import experience_service as service

TEST_PREFIX = f"codex_experience_pattern_{uuid.uuid4().hex}"


def _principal(
    user_id: int,
    *,
    organization_id: int | None = None,
    department_ids: tuple[int, ...] = (),
    position_ids: tuple[int, ...] = (),
) -> SimpleNamespace:
    return SimpleNamespace(
        user_id=user_id,
        organization_id=organization_id,
        department_ids=department_ids,
        position_ids=position_ids,
    )


def _snapshot(*, high_risk: bool = False, schema_version: int = 1) -> dict:
    return {
        "catalog_hash": f"catalog-{schema_version}",
        "capabilities": [{
            "capability_id": 71001,
            "module": "knowledge",
            "action": "search",
            "parameters": {
                "type": "object",
                "properties": {"query": {"type": "string"}, "version": {"const": schema_version}},
            },
            "execution_contract": {
                "side_effect_level": "create" if high_risk else "none",
                "resource_class": "fast",
            },
        }],
    }


@pytest_asyncio.fixture
async def db():
    async with AsyncSessionLocal() as session:
        yield session
        await session.rollback()
        await session.execute(
            delete(MemoryExperience).where(MemoryExperience.goal_signature.like(f"{TEST_PREFIX}%"))
        )
        await session.commit()


@pytest.fixture(autouse=True)
def disable_embedding(monkeypatch: pytest.MonkeyPatch):
    async def _no_embedding(_text: str):
        return None

    monkeypatch.setattr(service.embedding_service, "_compute_embedding", _no_embedding)


@pytest.mark.asyncio
async def test_user_pattern_is_sanitized_verified_and_owner_isolated(db) -> None:
    marker = f"{TEST_PREFIX}_owner open /Users/alice/private.pdf file_id=123456 alice@example.com"
    principal = _principal(981001)
    snapshot = _snapshot()
    payload = {
        "trigger_condition": marker,
        "steps": [{
            "id": "a1",
            "capability": "knowledge__search",
            "arguments": {"file_id": 123456, "path": "/Users/alice/private.pdf"},
        }],
        "tools_used": ["knowledge__search"],
        "owner_id": principal.user_id,
        "principal_context": principal,
        "capability_snapshot": snapshot,
        "preconditions": {"file_id": 123456, "path": "/Users/alice/private.pdf"},
        "completion_evidence": {"customer": "Acme", "result": "found"},
    }
    first = await service._save_experience(db, **payload)
    second = await service._save_experience(db, **payload)
    assert first["status"] == "candidate"
    assert second["status"] == "verified"

    exp = await db.get(MemoryExperience, second["id"])
    assert exp is not None
    assert "/Users/alice" not in exp.goal_signature
    assert "alice@example.com" not in exp.goal_signature
    assert "123456" not in exp.goal_signature
    assert exp.preconditions["file_id"] == "<redacted>"
    assert exp.completion_evidence["customer"] == "<redacted>"
    assert exp.action_pattern == [{
        "id": "a1",
        "capability": "knowledge__search",
        "depends_on": [],
        "expected_references": [],
    }]

    own = await service._match_experience(
        db,
        TEST_PREFIX,
        owner_id=principal.user_id,
        principal_context=principal,
        capability_snapshot=snapshot,
    )
    other = await service._match_experience(
        db,
        TEST_PREFIX,
        owner_id=981002,
        principal_context=_principal(981002),
        capability_snapshot=snapshot,
    )
    assert [item["id"] for item in own] == [second["id"]]
    assert other == []


@pytest.mark.asyncio
async def test_six_scope_visibility_and_conversation_isolation(db) -> None:
    principal = _principal(
        982001,
        organization_id=982100,
        department_ids=(982200,),
        position_ids=(982300,),
    )
    snapshot = _snapshot()
    contract_hash = service._capability_contract_hash(snapshot["capabilities"][0])
    action_pattern = [{
        "id": "a1",
        "capability": "knowledge__search",
        "depends_on": [],
        "expected_references": [],
    }]
    scopes = [
        ("global", None, None),
        ("organization", 982100, None),
        ("department", 982200, None),
        ("position", 982300, None),
        ("user", 982001, 982001),
        ("conversation", 982400, 982001),
        ("conversation", 982401, 982001),
    ]
    for index, (scope_type, scope_id, owner_id) in enumerate(scopes):
        marker = f"{TEST_PREFIX}_scope visible {index}"
        db.add(MemoryExperience(
            created_by_user_id=owner_id,
            scope_type=scope_type,
            scope_id=scope_id,
            goal_signature=marker,
            action_pattern=action_pattern,
            capability_ids=[71001],
            capability_contract_hashes={"knowledge__search": contract_hash},
            success_count=3,
            distinct_user_count=2,
            contributor_user_ids=[982001, 982002],
            confidence=1.0,
            status="active",
            privacy_status="sanitized",
        ))
    await db.commit()

    visible = await service._match_experience(
        db,
        f"{TEST_PREFIX}_scope",
        limit=20,
        owner_id=982001,
        principal_context=principal,
        capability_snapshot=snapshot,
        conversation_id=982400,
    )
    assert {item["scope_type"] for item in visible} == {
        "global", "organization", "department", "position", "user", "conversation",
    }
    assert sum(item["scope_type"] == "conversation" for item in visible) == 1

    unrelated = await service._match_experience(
        db,
        f"{TEST_PREFIX}_scope",
        limit=20,
        owner_id=982999,
        principal_context=_principal(982999),
        capability_snapshot=snapshot,
        conversation_id=982400,
    )
    assert {item["scope_type"] for item in unrelated} == {"global"}


@pytest.mark.asyncio
async def test_contract_hash_change_invalidates_before_return(db) -> None:
    principal = _principal(983001)
    marker = f"{TEST_PREFIX}_contract lookup"
    payload = {
        "trigger_condition": marker,
        "steps": [{"capability": "knowledge__search"}],
        "owner_id": principal.user_id,
        "principal_context": principal,
        "capability_snapshot": _snapshot(schema_version=1),
    }
    await service._save_experience(db, **payload)
    saved = await service._save_experience(db, **payload)
    current = await service._match_experience(
        db,
        marker,
        owner_id=principal.user_id,
        principal_context=principal,
        capability_snapshot=_snapshot(schema_version=1),
    )
    stale = await service._match_experience(
        db,
        marker,
        owner_id=principal.user_id,
        principal_context=principal,
        capability_snapshot=_snapshot(schema_version=2),
    )
    assert [item["id"] for item in current] == [saved["id"]]
    assert stale == []


@pytest.mark.asyncio
async def test_high_risk_department_promotion_requires_admin_review(db) -> None:
    marker = f"{TEST_PREFIX}_review publish"
    snapshot = _snapshot(high_risk=True)
    for user_id in (984001, 984002):
        await service._save_experience(
            db,
            marker,
            [{"capability": "knowledge__search"}],
            owner_id=user_id,
            principal_context=_principal(user_id, department_ids=(984200,)),
            capability_snapshot=snapshot,
        )
    result = await db.execute(select(MemoryExperience).where(
        MemoryExperience.scope_type == "department",
        MemoryExperience.scope_id == 984200,
        MemoryExperience.goal_signature == marker,
    ))
    department = result.scalar_one()
    assert department.status == "review_pending"
    assert department.requires_review is True

    before_review = await service._match_experience(
        db,
        marker,
        owner_id=984003,
        principal_context=_principal(984003, department_ids=(984200,)),
        capability_snapshot=snapshot,
    )
    assert all(item["scope_type"] != "department" for item in before_review)

    reviewed = await service._review_experience(
        db, department.id, "approve", reviewer_id=984999, note="marker approved"
    )
    assert reviewed["status"] == "active"
    after_review = await service._match_experience(
        db,
        marker,
        owner_id=984003,
        principal_context=_principal(984003, department_ids=(984200,)),
        capability_snapshot=snapshot,
    )
    assert any(item["id"] == department.id for item in after_review)


@pytest.mark.asyncio
async def test_low_risk_global_promotion_requires_cross_department_users(db) -> None:
    marker = f"{TEST_PREFIX}_global shared"
    snapshot = _snapshot()
    observations = (
        (985001, 985200),
        (985002, 985200),
        (985003, 985201),
    )
    for user_id, department_id in observations:
        await service._save_experience(
            db,
            marker,
            [{"capability": "knowledge__search"}],
            owner_id=user_id,
            principal_context=_principal(user_id, department_ids=(department_id,)),
            capability_snapshot=snapshot,
        )
    result = await db.execute(select(MemoryExperience).where(
        MemoryExperience.scope_type == "global",
        MemoryExperience.goal_signature == marker,
    ))
    global_pattern = result.scalar_one()
    assert global_pattern.status == "active"
    assert global_pattern.distinct_user_count == 3
    assert set(global_pattern.contributor_department_ids) == {985200, 985201}

    visible = await service._match_experience(
        db,
        marker,
        owner_id=985999,
        principal_context=_principal(985999),
        capability_snapshot=snapshot,
    )
    shared = next(item for item in visible if item["id"] == global_pattern.id)
    assert shared["source_conversation_id"] is None
    assert "contributor_user_ids" not in shared


@pytest.mark.asyncio
async def test_personal_preference_is_never_projected_to_shared_scopes(db) -> None:
    marker = f"{TEST_PREFIX}_preference 我的个人偏好是使用正式语气"
    snapshot = _snapshot()
    for user_id in (985501, 985502):
        await service._save_experience(
            db,
            marker,
            [{"capability": "knowledge__search"}],
            owner_id=user_id,
            principal_context=_principal(user_id, department_ids=(985600,)),
            capability_snapshot=snapshot,
            preconditions={"style": "formal"},
        )
    shared = await db.execute(select(MemoryExperience).where(
        MemoryExperience.goal_signature.like(f"{TEST_PREFIX}_preference%"),
        MemoryExperience.scope_type.in_({"global", "organization", "department", "position"}),
    ))
    assert shared.scalars().all() == []


@pytest.mark.asyncio
async def test_repeated_failure_suspends_visible_pattern(db) -> None:
    marker = f"{TEST_PREFIX}_failure"
    principal = _principal(986001)
    snapshot = _snapshot()
    saved = None
    for _ in range(2):
        saved = await service._save_experience(
            db,
            marker,
            [{"capability": "knowledge__search"}],
            owner_id=principal.user_id,
            principal_context=principal,
            capability_snapshot=snapshot,
        )
    assert saved is not None and saved["status"] == "verified"
    for index in range(3):
        feedback = await service._experience_feedback(
            db,
            saved["id"],
            False,
            note=f"failure {index}",
            owner_id=principal.user_id,
            principal_context=principal,
            capability_snapshot=snapshot,
        )
    assert feedback["status"] == "suspended"
    assert await service._match_experience(
        db,
        marker,
        owner_id=principal.user_id,
        principal_context=principal,
        capability_snapshot=snapshot,
    ) == []
