#!/usr/bin/env python3
"""Repair missing framework upload bytes from an enterprise source folder.

This script does not import new logical files. It only restores physical
content for file records already present in the framework file table.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = PROJECT_ROOT / "backend"
for path in (PROJECT_ROOT, BACKEND_ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from app.database import AsyncSessionLocal
from app.models.file import File
from sqlalchemy import select

from modules.knowledge.backend.models import KbSourceFileManifest
from modules.knowledge.backend.services.enterprise_import_service import (
    _file_md5,
    _normalize_extensions,
    _repair_existing_target_storage,
    _storage_file_missing,
    is_ignored_source_path,
    resolve_enterprise_source_root,
)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", required=True)
    parser.add_argument("--owner-id", type=int, required=True)
    parser.add_argument("--target-root-name", default="企业微盘导入")
    parser.add_argument("--extensions", nargs="*", default=None)
    parser.add_argument("--limit", type=int, default=0, help="0 means no limit")
    parser.add_argument("--apply", action="store_true", help="write repaired files")
    parser.add_argument(
        "--scan-all-md5",
        action="store_true",
        help="compute md5 for every source file and match missing records by md5 even when names differ",
    )
    parser.add_argument("--write-plan", default="", help="optional path to write matched repair candidates as JSON")
    parser.add_argument(
        "--include-ignored-source-paths",
        action="store_true",
        help="allow manual repair scans to include normally ignored folders such as $RECYCLE.BIN",
    )
    return parser


def _file_full_name(file: File) -> str:
    return f"{file.name}.{file.extension}" if file.extension else file.name


def _iter_repair_source_files(source_root: Path, extensions: set[str], *, include_ignored: bool) -> list[Path]:
    files: list[Path] = []
    for path in source_root.rglob("*"):
        if not include_ignored and is_ignored_source_path(path):
            continue
        if path.is_symlink() or not path.is_file():
            continue
        resolved_path = path.resolve()
        if not resolved_path.is_relative_to(source_root):
            continue
        ext = path.suffix.lower().lstrip(".")
        if ext == "tif":
            ext = "tiff"
        if ext not in extensions:
            continue
        files.append(path)
    return sorted(files, key=lambda item: str(item.relative_to(source_root)))


async def _run(args: argparse.Namespace) -> dict:
    source_root = resolve_enterprise_source_root(args.source_root)
    extensions = _normalize_extensions(args.extensions)
    scanned = 0
    matched = 0
    missing = 0
    repaired = 0
    skipped = 0
    failed = 0
    md5_scanned = 0
    md5_size_filtered = 0
    md5_matched = 0
    samples: list[dict] = []
    repair_plan: list[dict] = []
    limit = max(0, int(args.limit or 0))
    seen_file_ids: set[int] = set()

    async with AsyncSessionLocal() as db:
        manifest_stmt = (
            select(KbSourceFileManifest, File)
            .join(File, File.id == KbSourceFileManifest.file_id)
            .where(
                KbSourceFileManifest.owner_id == args.owner_id,
                KbSourceFileManifest.source_root == str(source_root),
                KbSourceFileManifest.file_id.is_not(None),
                File.owner_id == args.owner_id,
                File.deleted.is_(False),
                File.extension.in_(extensions),
            )
            .order_by(KbSourceFileManifest.id.asc())
        )
        for manifest, file in (await db.execute(manifest_stmt)).all():
            scanned += 1
            if limit and missing >= limit:
                break
            seen_file_ids.add(int(file.id))
            if not _storage_file_missing(file):
                continue
            source_path = Path(manifest.source_path).expanduser()
            if source_path.is_symlink() or not source_path.exists() or not source_path.is_file():
                skipped += 1
                samples.append({
                    "path": str(source_path),
                    "file_id": int(file.id),
                    "status": "source_missing",
                })
                continue
            resolved_source = source_path.resolve()
            if not resolved_source.is_relative_to(source_root):
                skipped += 1
                samples.append({
                    "path": str(source_path),
                    "file_id": int(file.id),
                    "status": "source_outside_root",
                })
                continue
            md5_hash = _file_md5(resolved_source)
            if file.md5_hash and file.md5_hash != md5_hash:
                skipped += 1
                samples.append({
                    "path": str(resolved_source.relative_to(source_root)),
                    "file_id": int(file.id),
                    "status": "md5_mismatch",
                })
                continue
            matched += 1
            missing += 1
            item = {
                "path": str(resolved_source.relative_to(source_root)),
                "file_id": int(file.id),
                "storage_path": file.storage_path,
                "status": "missing",
            }
            if args.apply:
                try:
                    did_repair = await _repair_existing_target_storage(
                        db,
                        file=file,
                        source_path=resolved_source,
                        md5_hash=md5_hash,
                    )
                except Exception as exc:
                    failed += 1
                    item["status"] = "repair_failed"
                    item["error"] = str(exc)[:500]
                    samples.append(item)
                    continue
                if did_repair:
                    repaired += 1
                    item["status"] = "repaired"
                    item["storage_path"] = file.storage_path
            samples.append(item)
            repair_plan.append(item)
        if not limit or missing < limit:
            candidates = (
                await db.execute(
                    select(File).where(
                        File.owner_id == args.owner_id,
                        File.deleted.is_(False),
                        File.extension.in_(extensions),
                    )
                )
            ).scalars().all()
            missing_by_name: dict[str, list[File]] = {}
            for file in candidates:
                if int(file.id) in seen_file_ids or not _storage_file_missing(file):
                    continue
                missing_by_name.setdefault(_file_full_name(file), []).append(file)

            for source_path in _iter_repair_source_files(
                source_root,
                extensions,
                include_ignored=bool(args.include_ignored_source_paths),
            ):
                scanned += 1
                if limit and missing >= limit:
                    break
                name_matches = missing_by_name.get(source_path.name)
                if not name_matches:
                    continue
                md5_hash = _file_md5(source_path)
                for file in list(name_matches):
                    if file.md5_hash and file.md5_hash != md5_hash:
                        continue
                    matched += 1
                    missing += 1
                    item = {
                        "path": str(source_path.relative_to(source_root)),
                        "file_id": int(file.id),
                        "storage_path": file.storage_path,
                        "status": "missing",
                    }
                    if args.apply:
                        try:
                            did_repair = await _repair_existing_target_storage(
                                db,
                                file=file,
                                source_path=source_path,
                                md5_hash=md5_hash,
                            )
                        except Exception as exc:
                            failed += 1
                            item["status"] = "repair_failed"
                            item["error"] = str(exc)[:500]
                            samples.append(item)
                            continue
                        if did_repair:
                            repaired += 1
                            item["status"] = "repaired"
                            item["storage_path"] = file.storage_path
                    samples.append(item)
                    repair_plan.append(item)
                    seen_file_ids.add(int(file.id))
                    name_matches.remove(file)
                    if limit and missing >= limit:
                        break

            if args.scan_all_md5 and (not limit or missing < limit):
                missing_by_md5: dict[str, list[File]] = {}
                wanted_sizes: set[int] = set()
                for file in candidates:
                    if int(file.id) in seen_file_ids or not _storage_file_missing(file):
                        continue
                    md5_hash = str(file.md5_hash or "").strip().lower()
                    if not md5_hash:
                        continue
                    missing_by_md5.setdefault(md5_hash, []).append(file)
                    wanted_sizes.add(int(file.size or 0))

                for source_path in _iter_repair_source_files(
                    source_root,
                    extensions,
                    include_ignored=bool(args.include_ignored_source_paths),
                ):
                    if limit and missing >= limit:
                        break
                    if wanted_sizes:
                        try:
                            source_size = source_path.stat().st_size
                        except OSError:
                            continue
                        if int(source_size) not in wanted_sizes:
                            md5_size_filtered += 1
                            continue
                    md5_hash = _file_md5(source_path)
                    md5_scanned += 1
                    md5_matches = missing_by_md5.get(md5_hash)
                    if not md5_matches:
                        continue
                    for file in list(md5_matches):
                        if limit and missing >= limit:
                            break
                        matched += 1
                        md5_matched += 1
                        missing += 1
                        item = {
                            "path": str(source_path.relative_to(source_root)),
                            "file_id": int(file.id),
                            "storage_path": file.storage_path,
                            "status": "missing",
                            "match_reason": "md5_full_scan",
                        }
                        if args.apply:
                            try:
                                did_repair = await _repair_existing_target_storage(
                                    db,
                                    file=file,
                                    source_path=source_path,
                                    md5_hash=md5_hash,
                                )
                            except Exception as exc:
                                failed += 1
                                item["status"] = "repair_failed"
                                item["error"] = str(exc)[:500]
                                samples.append(item)
                                repair_plan.append(item)
                                continue
                            if did_repair:
                                repaired += 1
                                item["status"] = "repaired"
                                item["storage_path"] = file.storage_path
                        samples.append(item)
                        repair_plan.append(item)
                        seen_file_ids.add(int(file.id))
                        md5_matches.remove(file)
                    if not md5_matches:
                        missing_by_md5.pop(md5_hash, None)

    result = {
        "dry_run": not args.apply,
        "source_root": str(source_root),
        "owner_id": args.owner_id,
        "target_root_name": args.target_root_name,
        "extensions": sorted(extensions),
        "scanned": scanned,
        "matched_existing_records": matched,
        "missing_physical_files": missing,
        "repaired": repaired,
        "skipped": skipped,
        "failed": failed,
        "name_md5_fallback": True,
        "scan_all_md5": bool(args.scan_all_md5),
        "include_ignored_source_paths": bool(args.include_ignored_source_paths),
        "md5_scanned": md5_scanned,
        "md5_size_filtered": md5_size_filtered,
        "md5_matched": md5_matched,
        "samples": samples[:100],
    }
    if args.write_plan:
        plan_path = Path(args.write_plan).expanduser()
        plan_path.parent.mkdir(parents=True, exist_ok=True)
        plan_path.write_text(json.dumps(repair_plan, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
        result["plan_path"] = str(plan_path)
        result["plan_items"] = len(repair_plan)
    return result


def main() -> int:
    args = _build_parser().parse_args()
    result = asyncio.run(_run(args))
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
