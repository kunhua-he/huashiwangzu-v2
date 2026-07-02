"""Tests for dev_toolkit SQL read-only guard."""

import pytest

from dev_toolkit.sql_guard import check_sql_readonly, readonly_psql_env


@pytest.mark.parametrize(
    "query",
    [
        "SELECT 1",
        "select 'DROP TABLE is just text'",
        "WITH rows AS (SELECT 1 AS n) SELECT n FROM rows",
        "EXPLAIN SELECT * FROM framework_file_items",
        "SHOW server_version",
        "VALUES (1), (2);",
    ],
)
def test_check_sql_readonly_accepts_single_readonly_statement(query: str) -> None:
    check_sql_readonly(query)


@pytest.mark.parametrize(
    "query",
    [
        "SELECT 1; DELETE FROM framework_file_items",
        "SELECT 1; SELECT 2;",
        "SELECT 1 -- trailing comment",
        "SELECT /* hidden */ 1",
        "WITH gone AS (DELETE FROM framework_file_items RETURNING *) SELECT * FROM gone",
        "EXPLAIN UPDATE framework_file_items SET name = 'x'",
        "SELECT * INTO tmp_copy FROM framework_file_items",
        "COPY framework_file_items TO STDOUT",
        "DO $$ BEGIN DELETE FROM framework_file_items; END $$",
    ],
)
def test_check_sql_readonly_rejects_mutating_or_ambiguous_sql(query: str) -> None:
    with pytest.raises(ValueError):
        check_sql_readonly(query)


def test_readonly_psql_env_forces_readonly_transaction() -> None:
    env = readonly_psql_env({"PGOPTIONS": "-c statement_timeout=1000"})

    assert "-c statement_timeout=1000" in env["PGOPTIONS"]
    assert "-c default_transaction_read_only=on" in env["PGOPTIONS"]
