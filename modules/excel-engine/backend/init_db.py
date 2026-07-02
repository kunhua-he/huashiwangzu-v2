"""Startup schema repair for excel-engine tables."""

import asyncio
import logging

from app.database import engine
from app.models.base import Base
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger("v2.excel_engine").getChild("init_db")


_INDEX_STATEMENTS = [
    "ALTER TABLE excel_workbooks DROP CONSTRAINT IF EXISTS excel_workbooks_state_key_key",
    "DROP INDEX IF EXISTS ux_excel_wb_state_key",
    "CREATE INDEX IF NOT EXISTS idx_excel_wb_state_key ON excel_workbooks(state_key)",
    (
        "CREATE UNIQUE INDEX IF NOT EXISTS ux_excel_wb_owner_state_key "
        "ON excel_workbooks(owner_id, state_key)"
    ),
]


async def ensure_excel_tables(db: AsyncSession) -> None:
    from .models import (  # noqa: F401
        ExcelCell,
        ExcelColWidth,
        ExcelHistory,
        ExcelRedoStack,
        ExcelRowHeight,
        ExcelSheet,
        ExcelVersion,
        ExcelWorkbook,
    )

    excel_tables = [table for name, table in Base.metadata.tables.items() if name.startswith("excel_")]
    async with engine.begin() as conn:
        await conn.run_sync(lambda c: Base.metadata.create_all(c, tables=excel_tables))
    logger.info("Ensured %d excel_* tables exist", len(excel_tables))


async def ensure_excel_indexes(db: AsyncSession) -> None:
    for stmt in _INDEX_STATEMENTS:
        try:
            await db.execute(text(stmt))
        except Exception as exc:
            logger.warning("Excel index migration skipped (%s): %s", stmt[:80], exc)
    await db.commit()


async def run_init(db: AsyncSession) -> None:
    await ensure_excel_tables(db)
    await ensure_excel_indexes(db)


def _run_startup_init() -> None:
    async def _init() -> None:
        from app.database import AsyncSessionLocal

        async with AsyncSessionLocal() as db:
            await run_init(db)

    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = None

    if loop is not None and loop.is_running():
        asyncio.ensure_future(_init())
        logger.info("Scheduled excel-engine startup init on running event loop")
    else:
        try:
            asyncio.run(_init())
            logger.info("Excel-engine startup init complete")
        except Exception as exc:
            logger.warning("Excel-engine startup init skipped: %s", exc)
