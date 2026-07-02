"""SQL read-only guard for the project toolkit.

The toolkit SQL helper is intentionally diagnostic-only.  This guard rejects
anything that is not a single, comment-free read-only statement before psql is
allowed to see it, then the caller also runs psql in read-only transaction mode.
"""

from __future__ import annotations

import os
import re
from typing import Mapping

ALLOWED_PREFIXES = ("SELECT", "WITH", "EXPLAIN", "SHOW", "DESCRIBE", "VALUES")
FORBIDDEN_KEYWORDS = re.compile(
    r"\b("
    r"INSERT|UPDATE|DELETE|DROP|ALTER|TRUNCATE|CREATE|GRANT|REVOKE|EXECUTE|CALL|MERGE|"
    r"COPY|VACUUM|LOCK|SET|RESET|DO|COMMENT|REFRESH|CLUSTER|DISCARD|PREPARE|DEALLOCATE|"
    r"IMPORT|EXPORT|INTO"
    r")\b",
    re.IGNORECASE,
)
DOLLAR_QUOTE = re.compile(r"\$[A-Za-z_][A-Za-z0-9_]*\$|\$\$")


def _consume_quoted_text(query: str, start: int, quote: str) -> int:
    i = start + 1
    while i < len(query):
        if query[i] == quote:
            if i + 1 < len(query) and query[i + 1] == quote:
                i += 2
                continue
            return i + 1
        i += 1
    raise ValueError("SQL 引号未闭合，已拒绝执行")


def _mask_literals_and_reject_comments(query: str) -> str:
    masked: list[str] = []
    i = 0
    while i < len(query):
        pair = query[i:i + 2]
        if pair in {"--", "/*"}:
            raise ValueError("SQL 注释不允许出现在工具台只读查询中，已拒绝执行")
        if query[i] in {"'", '"'}:
            end = _consume_quoted_text(query, i, query[i])
            masked.append(" " * (end - i))
            i = end
            continue
        if query[i] == "$":
            match = DOLLAR_QUOTE.match(query, i)
            if match:
                tag = match.group(0)
                end = query.find(tag, match.end())
                if end < 0:
                    raise ValueError("SQL dollar-quoted 字符串未闭合，已拒绝执行")
                end += len(tag)
                masked.append(" " * (end - i))
                i = end
                continue
        masked.append(query[i])
        i += 1
    return "".join(masked)


def _single_statement_without_literals(query: str) -> str:
    statement = _mask_literals_and_reject_comments(query).strip()
    if not statement:
        raise ValueError("SQL 查询不能为空")
    semicolon_count = statement.count(";")
    if semicolon_count:
        if semicolon_count == 1 and statement.endswith(";"):
            statement = statement[:-1].rstrip()
        else:
            raise ValueError("只允许单条只读 SQL；多语句或分号链已拒绝执行")
    return statement


def _first_keyword(statement: str) -> str:
    candidate = statement.lstrip()
    while candidate.startswith("("):
        candidate = candidate[1:].lstrip()
    match = re.match(r"[A-Za-z_][A-Za-z0-9_]*", candidate)
    if not match:
        raise ValueError("无法识别 SQL 起始关键字，已拒绝执行")
    return match.group(0).upper()


def check_sql_readonly(query: str) -> None:
    """Raise ValueError unless *query* is one read-only SQL statement."""
    statement = _single_statement_without_literals(query)
    first_keyword = _first_keyword(statement)
    if first_keyword not in ALLOWED_PREFIXES:
        allowed = "/".join(ALLOWED_PREFIXES)
        raise ValueError(f"只允许只读查询 ({allowed})，检测到不允许的语句: {query[:80]}")
    forbidden = FORBIDDEN_KEYWORDS.search(statement)
    if forbidden:
        raise ValueError(f"只读 SQL 中检测到危险关键字 {forbidden.group(1).upper()}，已拒绝执行")


def readonly_psql_env(base_env: Mapping[str, str] | None = None) -> dict[str, str]:
    """Return an environment that forces PostgreSQL transactions to read-only."""
    env = dict(base_env or os.environ)
    pgoptions = env.get("PGOPTIONS", "").strip()
    readonly_option = "-c default_transaction_read_only=on"
    env["PGOPTIONS"] = f"{pgoptions} {readonly_option}".strip()
    return env
