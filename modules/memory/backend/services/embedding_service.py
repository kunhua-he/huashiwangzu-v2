"""Memory embedding service — bge-m3 embedding computation and vector storage.

Extracted from router.py to follow Router → Service → Model layering.
"""
import logging
from sqlalchemy import text
from app.database import AsyncSessionLocal

logger = logging.getLogger("v2.memory").getChild("embedding_service")

async def _compute_embedding(text: str) -> list[float] | None:
    """Compute embedding via framework model_services. Returns None on failure."""
    try:
        from app.services.model_services import get_embedding
        return await get_embedding(text[:2048])
    except Exception as e:
        logger.warning("Embedding computation failed: %s", e)
        return None



async def _update_embedding_sql(db, memory_id: int, vec_literal: str) -> None:
    """Shared helper: update embedding vector using parameterized SQL."""
    # 用 CAST(...) 而非 ::vector——:embedding 绑定参数紧挨 :: 会和绑定语法冲突, asyncpg编译出野冒号致语法错
    sql = "UPDATE memory_records SET embedding = CAST(:embedding AS vector) WHERE id = :id"
    await db.execute(text(sql), {"embedding": vec_literal, "id": memory_id})
    await db.commit()
