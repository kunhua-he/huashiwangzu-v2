#!/usr/bin/env python3
"""Report source-name candidates for missing framework upload files.

This is read-only. It lists missing DB file records and scans a source root for
same-name or near-same-name candidates before any MD5 repair is attempted.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
import unicodedata
from collections import defaultdict
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = PROJECT_ROOT / "backend"
for path in (PROJECT_ROOT, BACKEND_ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from app.database import AsyncSessionLocal
from app.models.file import File
from sqlalchemy import select

from modules.knowledge.backend.services.enterprise_import_service import (
    _iter_source_files,
    _normalize_extensions,
    _storage_file_missing,
    resolve_enterprise_source_root,
)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", required=True)
    parser.add_argument("--owner-id", type=int, required=True)
    parser.add_argument("--extensions", nargs="*", default=None)
    parser.add_argument("--write-report", required=True)
    parser.add_argument("--write-names", required=True)
    parser.add_argument("--sample-limit", type=int, default=200)
    return parser


def _full_name(file: File) -> str:
    return f"{file.name}.{file.extension}" if file.extension else file.name


def _normalize_name(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).casefold()
    return re.sub(r"[\s_\-·.（）()【】\\[\\]《》<>]+", "", normalized)


async def _load_missing_files(owner_id: int, extensions: set[str]) -> list[File]:
    async with AsyncSessionLocal() as db:
        files = (
            await db.execute(
                select(File)
                .where(
                    File.owner_id == owner_id,
                    File.deleted.is_(False),
                    File.extension.in_(extensions),
                )
                .order_by(File.id.asc())
            )
        ).scalars().all()
    return [file for file in files if _storage_file_missing(file)]


def _append_limited(target: list[dict], item: dict, limit: int) -> None:
    if len(target) < limit:
        target.append(item)


async def _run(args: argparse.Namespace) -> dict:
    source_root = resolve_enterprise_source_root(args.source_root)
    extensions = _normalize_extensions(args.extensions)
    missing_files = await _load_missing_files(args.owner_id, extensions)
    sample_limit = max(0, int(args.sample_limit or 0))

    exact_index: dict[str, list[Path]] = defaultdict(list)
    casefold_index: dict[str, list[Path]] = defaultdict(list)
    normalized_index: dict[str, list[Path]] = defaultdict(list)
    source_scanned = 0
    for source_path in _iter_source_files(source_root, extensions):
        source_scanned += 1
        exact_index[source_path.name].append(source_path)
        casefold_index[source_path.name.casefold()].append(source_path)
        normalized_index[_normalize_name(source_path.name)].append(source_path)

    missing_names: list[dict] = []
    exact_matches: list[dict] = []
    casefold_matches: list[dict] = []
    normalized_matches: list[dict] = []
    unmatched: list[dict] = []
    matched_file_ids: set[int] = set()

    for file in missing_files:
        file_id = int(file.id)
        name = _full_name(file)
        entry = {
            "file_id": file_id,
            "name": name,
            "extension": (file.extension or "").lower(),
            "size": int(file.size or 0),
            "md5_hash": file.md5_hash,
            "storage_path": file.storage_path,
        }
        missing_names.append(entry)

        exact = exact_index.get(name, [])
        if exact:
            matched_file_ids.add(file_id)
            match = {
                **entry,
                "match_type": "exact",
                "candidate_count": len(exact),
                "candidates": [str(path.relative_to(source_root)) for path in exact[:10]],
            }
            _append_limited(exact_matches, match, sample_limit)
            continue

        casefold = casefold_index.get(name.casefold(), [])
        if casefold:
            matched_file_ids.add(file_id)
            match = {
                **entry,
                "match_type": "casefold",
                "candidate_count": len(casefold),
                "candidates": [str(path.relative_to(source_root)) for path in casefold[:10]],
            }
            _append_limited(casefold_matches, match, sample_limit)
            continue

        normalized = normalized_index.get(_normalize_name(name), [])
        if normalized:
            matched_file_ids.add(file_id)
            match = {
                **entry,
                "match_type": "normalized",
                "candidate_count": len(normalized),
                "candidates": [str(path.relative_to(source_root)) for path in normalized[:10]],
            }
            _append_limited(normalized_matches, match, sample_limit)
            continue

        _append_limited(unmatched, entry, sample_limit)

    names_path = Path(args.write_names).expanduser()
    names_path.parent.mkdir(parents=True, exist_ok=True)
    names_path.write_text(
        "\n".join(
            f"{item['file_id']}\t{item['extension']}\t{item['size']}\t{item['md5_hash']}\t{item['name']}"
            for item in missing_names
        )
        + ("\n" if missing_names else ""),
        encoding="utf-8",
    )

    report = {
        "source_root": str(source_root),
        "owner_id": args.owner_id,
        "extensions": sorted(extensions),
        "source_scanned": source_scanned,
        "missing_total": len(missing_files),
        "matched_total": len(matched_file_ids),
        "unmatched_total": len(missing_files) - len(matched_file_ids),
        "exact_match_samples": exact_matches,
        "casefold_match_samples": casefold_matches,
        "normalized_match_samples": normalized_matches,
        "unmatched_samples": unmatched,
        "missing_names_path": str(names_path),
    }
    report_path = Path(args.write_report).expanduser()
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    report["report_path"] = str(report_path)
    return report


def main() -> int:
    args = _build_parser().parse_args()
    print(json.dumps(asyncio.run(_run(args)), ensure_ascii=False, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
