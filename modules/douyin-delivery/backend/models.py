"""DB models for douyin-delivery module."""

from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, JSON, Float, text
from app.models.base import Base


class DouyinProduct(Base):
    __tablename__ = "douyin_products"

    id = Column(Integer, primary_key=True, autoincrement=True)
    owner_id = Column(Integer, nullable=False, index=True)
    name = Column(String(200), nullable=False)
    category = Column(String(100), nullable=True, default="")
    selling_points = Column(JSON, nullable=True, comment="卖点列表")
    ingredients = Column(JSON, nullable=True, comment="成分列表")
    target_audience = Column(String(500), nullable=True, default="")
    brand = Column(String(100), nullable=True, default="俏小喵")
    notes = Column(Text, nullable=True, default="")
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP"))
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP"), onupdate=datetime.now(timezone.utc))
    deleted = Column(Boolean, nullable=False, default=False)


class DouyinScript(Base):
    __tablename__ = "douyin_scripts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    owner_id = Column(Integer, nullable=False, index=True)
    title = Column(String(300), nullable=False, default="")
    product_id = Column(Integer, nullable=True)
    product_name = Column(String(200), nullable=True, default="")
    channel = Column(String(50), nullable=False, default="local_push", comment="local_push/ocean_engine/qianchuan")
    hook = Column(Text, nullable=True, default="", comment="开头钩子")
    pain_point = Column(Text, nullable=True, default="", comment="痛点描述")
    selling_point = Column(Text, nullable=True, default="", comment="卖点展开")
    social_proof = Column(Text, nullable=True, default="", comment="信任背书")
    call_to_action = Column(Text, nullable=True, default="", comment="行动引导")
    full_script = Column(Text, nullable=True, default="", comment="完整口播稿")
    style_notes = Column(Text, nullable=True, default="", comment="拍摄/剪辑建议")
    hashtags = Column(JSON, nullable=True, comment="话题标签")
    suggested_titles = Column(JSON, nullable=True, comment="标题候选项")
    status = Column(String(20), nullable=False, default="draft")
    version = Column(Integer, nullable=False, default=1)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP"))
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP"), onupdate=datetime.now(timezone.utc))
    deleted = Column(Boolean, nullable=False, default=False)


class DouyinAdCopy(Base):
    __tablename__ = "douyin_ad_copies"

    id = Column(Integer, primary_key=True, autoincrement=True)
    owner_id = Column(Integer, nullable=False, index=True)
    product_id = Column(Integer, nullable=True)
    product_name = Column(String(200), nullable=True, default="")
    channel = Column(String(50), nullable=False, default="ocean_engine", comment="local_push/ocean_engine/qianchuan")
    ad_type = Column(String(50), nullable=False, default="feed", comment="feed/search/brand")
    title = Column(String(200), nullable=False, default="")
    headline = Column(String(100), nullable=True, default="", comment="短标题")
    description = Column(Text, nullable=True, default="", comment="广告描述")
    call_to_action = Column(String(50), nullable=True, default="立即购买", comment="行动号召按钮文案")
    target_audience_desc = Column(Text, nullable=True, default="", comment="定向人群描述")
    landing_page_suggestion = Column(String(500), nullable=True, default="", comment="落地页建议")
    status = Column(String(20), nullable=False, default="draft")
    version = Column(Integer, nullable=False, default=1)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP"))
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP"), onupdate=datetime.now(timezone.utc))
    deleted = Column(Boolean, nullable=False, default=False)


class DouyinCampaign(Base):
    __tablename__ = "douyin_campaigns"

    id = Column(Integer, primary_key=True, autoincrement=True)
    owner_id = Column(Integer, nullable=False, index=True)
    name = Column(String(300), nullable=False)
    channel = Column(String(50), nullable=False, default="local_push", comment="local_push/ocean_engine/qianchuan")
    status = Column(String(20), nullable=False, default="planning", comment="planning/running/paused/ended")
    budget = Column(Float, nullable=True, default=0)
    budget_type = Column(String(20), nullable=True, default="daily", comment="daily/total")
    start_date = Column(String(20), nullable=True, default="")
    end_date = Column(String(20), nullable=True, default="")
    target_audience = Column(JSON, nullable=True, comment="定向设置")
    product_ids = Column(JSON, nullable=True, comment="关联产品")
    script_ids = Column(JSON, nullable=True, comment="关联脚本")
    ad_copy_ids = Column(JSON, nullable=True, comment="关联文案")
    notes = Column(Text, nullable=True, default="")
    performance_metrics = Column(JSON, nullable=True, comment="ROI/CTR/CVR 数据")
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP"))
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP"), onupdate=datetime.now(timezone.utc))
    deleted = Column(Boolean, nullable=False, default=False)


class DouyinPrompt(Base):
    __tablename__ = "douyin_prompts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    owner_id = Column(Integer, nullable=False, index=True)
    key = Column(String(100), nullable=False)
    name = Column(String(200), nullable=False, default="")
    content = Column(Text, nullable=False)
    description = Column(Text, nullable=True, default="")
    category = Column(String(50), nullable=True, default="system")
    channel = Column(String(50), nullable=True, default="", comment="渠道筛选")
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP"))
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP"), onupdate=datetime.now(timezone.utc))
    deleted = Column(Boolean, nullable=False, default=False)
