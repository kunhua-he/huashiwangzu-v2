"""Local dev-toolkit authentication helpers.

The project toolkit runs on the developer machine with direct access to the
repo and database. It issues backend-compatible local tokens directly so stale
login credentials and rate limits cannot block MCP tooling itself.
"""
from __future__ import annotations

import base64
import argparse
import hashlib
import hmac
import json
import os
import time
from pathlib import Path
from typing import Any

try:
    import psycopg2
    from psycopg2.extras import RealDictCursor

    from dev_toolkit.config_loader import load_config
except ModuleNotFoundError:
    import psycopg2
    from config_loader import load_config
    from psycopg2.extras import RealDictCursor


def _read_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def _backend_jwt_settings(repo_root: Path) -> tuple[str, str, int]:
    env_file = _read_env_file(repo_root / "backend" / ".env")
    secret = os.environ.get("JWT_SECRET") or env_file.get("JWT_SECRET") or ""
    algorithm = os.environ.get("JWT_ALGORITHM") or env_file.get("JWT_ALGORITHM") or "HS256"
    expire_raw = os.environ.get("JWT_EXPIRE_MINUTES") or env_file.get("JWT_EXPIRE_MINUTES") or "1440"
    if not secret:
        raise RuntimeError("backend JWT_SECRET is not configured")
    if algorithm != "HS256":
        raise RuntimeError(f"unsupported JWT_ALGORITHM for dev toolkit token: {algorithm}")
    return secret, algorithm, int(expire_raw)


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _encode_hs256(payload: dict[str, Any], secret: str) -> str:
    header = {"alg": "HS256", "typ": "JWT"}
    signing_input = ".".join(
        [
            _b64url(json.dumps(header, separators=(",", ":")).encode("utf-8")),
            _b64url(json.dumps(payload, separators=(",", ":")).encode("utf-8")),
        ]
    )
    signature = hmac.new(secret.encode("utf-8"), signing_input.encode("ascii"), hashlib.sha256).digest()
    return f"{signing_input}.{_b64url(signature)}"


def _account_for_role(accounts: dict[str, Any], role: str) -> dict[str, Any]:
    account = accounts.get(role) if isinstance(accounts, dict) else None
    if isinstance(account, dict):
        return account
    fallback = accounts.get("admin") if isinstance(accounts, dict) else None
    return fallback if isinstance(fallback, dict) else {"role": role}


def _select_toolkit_user(db_dsn: str, account: dict[str, Any], role: str) -> dict[str, Any]:
    user_id = account.get("user_id")
    username = str(account.get("username") or "").strip()
    wanted_role = str(account.get("role") or role or "admin")
    query = """
        select id, username, display_name, role, session_version
        from framework_user_accounts
        where enabled = true
          and (
            (%s is not null and id = %s)
            or (%s <> '' and username = %s)
            or (%s = '' and %s is null and role = %s)
          )
        order by
          case when %s is not null and id = %s then 0 else 1 end,
          case when %s <> '' and username = %s then 0 else 1 end,
          id asc
        limit 1
    """
    user_id_param = int(user_id) if isinstance(user_id, int) or str(user_id or "").isdigit() else None
    params = (
        user_id_param,
        user_id_param,
        username,
        username,
        username,
        user_id_param,
        wanted_role,
        user_id_param,
        user_id_param,
        username,
        username,
    )
    with psycopg2.connect(db_dsn) as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(query, params)
        row = cur.fetchone()
    if not row:
        selector = f"user_id={user_id_param}" if user_id_param is not None else f"username={username!r}, role={wanted_role!r}"
        raise RuntimeError(f"no enabled toolkit user found for {selector}")
    return dict(row)


def issue_toolkit_token(
    repo_root: Path,
    *,
    role: str = "admin",
    accounts: dict[str, Any] | None = None,
    db_dsn: str | None = None,
) -> tuple[str, dict[str, Any], int]:
    """Issue a backend-compatible JWT for a local toolkit request."""
    config = load_config(repo_root)
    effective_accounts = accounts if accounts is not None else config.get("accounts", {})
    account = _account_for_role(effective_accounts, role)
    dsn = db_dsn or str(config.get("db_dsn") or "")
    if not dsn:
        raise RuntimeError("dev toolkit db_dsn is not configured")
    secret, _algorithm, expire_minutes = _backend_jwt_settings(repo_root)
    user = _select_toolkit_user(dsn, account, role)
    expires_at = int(time.time()) + expire_minutes * 60
    payload = {
        "sub": str(user["id"]),
        "role": str(user["role"]),
        "sv": int(user.get("session_version") or 0),
        "exp": expires_at,
    }
    return _encode_hs256(payload, secret), user, expires_at


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Issue a local backend-compatible dev toolkit token")
    parser.add_argument("--role", default="admin", choices=("admin", "editor", "viewer"))
    parser.add_argument("--repo-root", default=str(Path(__file__).resolve().parent.parent))
    args = parser.parse_args(argv)
    repo_root = Path(args.repo_root).resolve()
    token, user, expires_at = issue_toolkit_token(repo_root, role=args.role)
    print(json.dumps({
        "access_token": token,
        "token_type": "bearer",
        "expires_at": expires_at,
        "user": user,
    }, ensure_ascii=False, default=str))


if __name__ == "__main__":
    main()
