"""Memory module table initialization (idempotent)."""
import logging
from app.database import engine
from .models import AgentMemory
from app.models.base import Base

logger = logging.getLogger("v2.memory.init_db")

TABLES = [AgentMemory.__table__]


async def run_init() -> None:
    async with engine.begin() as conn:
        for table in TABLES:
            await conn.run_sync(table.create, checkfirst=True)
    logger.info("Memory tables ensured")
