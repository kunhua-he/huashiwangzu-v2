#!/usr/bin/env python3
"""Bulk-upload enterprise files into the knowledge module through public HTTP APIs."""

from __future__ import annotations

import argparse
import json
import mimetypes
import os
import time
from pathlib import Path
from urllib import error, request


SUPPORTED_EXTENSIONS = {
    ".pdf", ".docx", ".pptx", ".xlsx", ".csv", ".txt", ".md",
    ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp", ".svg",
}
VIDEO_EXTENSIONS = {".mp4", ".mov", ".avi", ".mkv", ".wmv", ".m4v", ".webm"}


def _json_request(base_url: str, path: str, payload: dict, token: str | None = None, timeout: int = 120) -> dict:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = request.Request(f"{base_url}{path}", data=body, headers=headers)
    with request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _get_json(base_url: str, path: str, token: str | None = None, timeout: int = 60) -> dict:
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = request.Request(f"{base_url}{path}", headers=headers)
    with request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _multipart_upload(base_url: str, path: Path, root: Path, token: str, timeout: int = 300) -> dict:
    boundary = f"----kb-bulk-{time.time_ns()}"
    rel_parent = path.parent.relative_to(root).as_posix()
    mime_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    head = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="relative_path"\r\n\r\n'
        f"企业微盘导入/{rel_parent}\r\n"
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="file"; filename="{path.name}"\r\n'
        f"Content-Type: {mime_type}\r\n\r\n"
    ).encode("utf-8")
    tail = f"\r\n--{boundary}--\r\n".encode("utf-8")
    body = head + path.read_bytes() + tail
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": f"multipart/form-data; boundary={boundary}",
        "Content-Length": str(len(body)),
    }
    req = request.Request(f"{base_url}/api/files/upload", data=body, headers=headers, method="POST")
    with request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _queue_depth(base_url: str) -> tuple[int, int]:
    try:
        health = _get_json(base_url, "/api/health")
    except Exception:
        return 0, 0
    queue = (((health.get("data") or {}).get("task_queue")) or {})
    return int(queue.get("pending") or 0), int(queue.get("running") or 0)


def _iter_files(root: Path, max_size: int) -> list[Path]:
    items: list[Path] = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        ext = path.suffix.lower()
        if ext in VIDEO_EXTENSIONS or ext not in SUPPORTED_EXTENSIONS:
            continue
        try:
            size = path.stat().st_size
        except OSError:
            continue
        if size <= 0 or size > max_size:
            continue
        items.append(path)
    return sorted(items, key=lambda p: (p.suffix.lower() not in {".pdf", ".docx", ".xlsx", ".pptx"}, p.stat().st_size))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True)
    parser.add_argument("--base-url", default="http://127.0.0.1:33000")
    parser.add_argument("--username", default=os.getenv("KB_BULK_USERNAME", "何焜华"))
    parser.add_argument("--password", default=os.getenv("KB_BULK_PASSWORD", ""))
    parser.add_argument("--limit", type=int, default=200)
    parser.add_argument("--max-size-mb", type=int, default=120)
    parser.add_argument("--queue-high-water", type=int, default=12)
    parser.add_argument("--sleep-seconds", type=float, default=5.0)
    args = parser.parse_args()

    if not args.password:
        raise SystemExit("KB_BULK_PASSWORD is required")

    root = Path(args.root).expanduser().resolve()
    login = _json_request(args.base_url, "/api/login", {"username": args.username, "password": args.password})
    token = login["data"]["access_token"]
    max_size = args.max_size_mb * 1024 * 1024
    files = _iter_files(root, max_size)[: args.limit]

    print(json.dumps({
        "event": "start",
        "root": str(root),
        "selected": len(files),
        "limit": args.limit,
        "max_size_mb": args.max_size_mb,
    }, ensure_ascii=False), flush=True)

    uploaded = 0
    skipped = 0
    failed = 0
    for idx, path in enumerate(files, start=1):
        while True:
            pending, running = _queue_depth(args.base_url)
            if pending + running < args.queue_high_water:
                break
            print(json.dumps({
                "event": "throttle",
                "pending": pending,
                "running": running,
                "queue_high_water": args.queue_high_water,
            }, ensure_ascii=False), flush=True)
            time.sleep(args.sleep_seconds)

        try:
            result = _multipart_upload(args.base_url, path, root, token)
            if result.get("success"):
                uploaded += 1
                data = result.get("data") or {}
                print(json.dumps({
                    "event": "uploaded",
                    "index": idx,
                    "file_id": data.get("id"),
                    "size": path.stat().st_size,
                    "path": str(path),
                }, ensure_ascii=False), flush=True)
            else:
                failed += 1
                print(json.dumps({"event": "failed", "index": idx, "path": str(path), "error": result.get("error")}, ensure_ascii=False), flush=True)
        except error.HTTPError as exc:
            body = exc.read().decode("utf-8", "replace")
            if exc.code == 409:
                skipped += 1
                print(json.dumps({"event": "skipped_conflict", "index": idx, "path": str(path)}, ensure_ascii=False), flush=True)
            else:
                failed += 1
                print(json.dumps({"event": "http_error", "index": idx, "code": exc.code, "path": str(path), "body": body[:500]}, ensure_ascii=False), flush=True)
        except Exception as exc:
            failed += 1
            print(json.dumps({"event": "error", "index": idx, "path": str(path), "error": str(exc)}, ensure_ascii=False), flush=True)

    pending, running = _queue_depth(args.base_url)
    print(json.dumps({
        "event": "done",
        "uploaded": uploaded,
        "skipped": skipped,
        "failed": failed,
        "pending": pending,
        "running": running,
    }, ensure_ascii=False), flush=True)
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
