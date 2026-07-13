"""Memory module models. memory_ prefix."""
from datetime import datetime, timezone

from app.models.base import Base, TimestampMixin
from pgvector.sqlalchemy import Vector
from sqlalchemy import BigInteger, Boolean, DateTime, Float, Integer, String, Text
from sqlalchemy import func as sa_func
from sqlalchemy import text as sa_text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column


class MemoryStableRule(Base, TimestampMixin):
    """稳定规则记忆：项目边界、用户偏好、硬约束、长期规则。不参与向量衰减。"""
    __tablename__ = "memory_stable_rules"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    owner_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    rule_type: Mapped[str] = mapped_column(String(32), nullable=False, comment="project_boundary / user_preference / hard_constraint / long_term_rule")
    content: Mapped[str] = mapped_column(Text, nullable=False, comment="规则文本")
    priority: Mapped[int] = mapped_column(Integer, default=0, comment="优先级，越高越重要")
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    source: Mapped[str | None] = mapped_column(String(64), nullable=True, comment="规则来源")
    hit_count: Mapped[int] = mapped_column(Integer, default=0, server_default=sa_text("0"), comment="被命中次数")


class MemoryChunk(Base):
    """Chunk 级记忆：最小粒度段落，保留原文溯源。"""
    __tablename__ = "memory_chunks"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    owner_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    memory_record_id: Mapped[int | None] = mapped_column(Integer, nullable=True, comment="所属蒸馏记忆 id（可空：未蒸馏的原始chunk）")
    chunk_index: Mapped[int] = mapped_column(Integer, default=0, comment="chunk 序号")
    text: Mapped[str] = mapped_column(Text, nullable=False, comment="chunk 原文")
    summary: Mapped[str | None] = mapped_column(Text, nullable=True, comment="chunk 级摘要")
    embedding: Mapped[list[float] | None] = mapped_column(Vector(1024), nullable=True, comment="bge-m3 1024维向量")
    source: Mapped[str | None] = mapped_column(String(32), nullable=True, comment="来源")
    conversation_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, comment="来源对话 id")
    provenance: Mapped[str | None] = mapped_column(Text, nullable=True, comment="溯源信息：来源文件、段落范围等")
    start_char: Mapped[int | None] = mapped_column(Integer, nullable=True, comment="在原文中的起始字符位置")
    end_char: Mapped[int | None] = mapped_column(Integer, nullable=True, comment="在原文中的结束字符位置")
    confidence: Mapped[float] = mapped_column(Float, default=1.0, server_default=sa_text("1.0"))
    access_count: Mapped[int] = mapped_column(Integer, default=0, server_default=sa_text("0"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=sa_func.now(), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=sa_func.now(), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class MemoryRecord(Base):
    __tablename__ = "memory_records"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    owner_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    text: Mapped[str] = mapped_column(Text, nullable=False, comment="原始层：完整记忆文本")
    summary: Mapped[str | None] = mapped_column(Text, nullable=True, comment="总结层：LLM 预蒸馏摘要")
    tags: Mapped[str | None] = mapped_column(String(256), nullable=True)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(1024), nullable=True, comment="bge-m3 1024维向量")
    confidence: Mapped[float] = mapped_column(Float, default=1.0, server_default=sa_text("1.0"), comment="置信度 0-1")
    recency_score: Mapped[float] = mapped_column(Float, default=1.0, server_default=sa_text("1.0"), comment="时效分，dream 衰减用")
    raw_id: Mapped[int | None] = mapped_column(Integer, nullable=True, comment="原始层记录 id，下钻用")
    conversation_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, comment="来源对话 id")
    source: Mapped[str | None] = mapped_column(String(32), nullable=True, comment="来源：auto-distill/user-save/rethink")
    memory_type: Mapped[str | None] = mapped_column(String(32), nullable=True, comment="类型标签：fact/preference/convention/…")
    keywords: Mapped[str | None] = mapped_column(Text, nullable=True, comment="关键词，逗号分隔")
    access_count: Mapped[int] = mapped_column(Integer, default=0, server_default=sa_text("0"), comment="被召回次数")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=sa_func.now(), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=sa_func.now(), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class MemoryLink(Base, TimestampMixin):
    """记忆链图：跨对话的语义关联边。"""
    __tablename__ = "memory_links"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    from_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True, comment="源记忆 id")
    to_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True, comment="目标记忆 id")
    relation: Mapped[str] = mapped_column(String(32), nullable=False, default="semantic_related", comment="关系：semantic_related/same_thread/succession")
    weight: Mapped[float] = mapped_column(Float, default=0.5, comment="边权重 0-1")
    owner_id: Mapped[int] = mapped_column(Integer, nullable=False, comment="owner 隔离")


class MemoryExperience(Base):
    """Structured, scope-aware projection of verified execution experience."""
    __tablename__ = "memory_experiences"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    scope_type: Mapped[str] = mapped_column(String(32), nullable=False, default="user", server_default=sa_text("'user'"))
    scope_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, index=True)
    goal_signature: Mapped[str] = mapped_column(Text, nullable=False, default="", server_default=sa_text("''"))
    goal_embedding: Mapped[list[float] | None] = mapped_column(Vector(1024), nullable=True)
    preconditions: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict, server_default=sa_text("'{}'::jsonb"))
    action_pattern: Mapped[list] = mapped_column(JSONB, nullable=False, default=list, server_default=sa_text("'[]'::jsonb"))
    completion_evidence: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict, server_default=sa_text("'{}'::jsonb"))
    capability_ids: Mapped[list[int]] = mapped_column(ARRAY(Integer), nullable=False, default=list, server_default=sa_text("'{}'::integer[]"))
    capability_contract_hashes: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict, server_default=sa_text("'{}'::jsonb"))
    success_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default=sa_text("1"))
    distinct_user_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default=sa_text("1"))
    failure_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default=sa_text("0"))
    failure_notes: Mapped[list] = mapped_column(JSONB, nullable=False, default=list, server_default=sa_text("'[]'::jsonb"))
    created_by_user_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    source_conversation_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    contributor_user_ids: Mapped[list[int]] = mapped_column(ARRAY(Integer), nullable=False, default=list, server_default=sa_text("'{}'::integer[]"))
    contributor_department_ids: Mapped[list[int]] = mapped_column(ARRAY(Integer), nullable=False, default=list, server_default=sa_text("'{}'::integer[]"))
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.5, server_default=sa_text("0.5"))
    last_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="candidate", server_default=sa_text("'candidate'"))
    risk_level: Mapped[str] = mapped_column(String(32), nullable=False, default="none", server_default=sa_text("'none'"))
    privacy_status: Mapped[str] = mapped_column(String(32), nullable=False, default="sanitized", server_default=sa_text("'sanitized'"))
    requires_review: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=sa_text("false"))
    reviewed_by: Mapped[int | None] = mapped_column(Integer, nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    review_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=sa_func.now(), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=sa_func.now(), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
