"""Tool guidance control plane service.

Provides CRUD for tool guides, versioning, rollback, candidate
promotion, and the merge-order injection for runtime guidance.

Error classification and degradation recipes (Task B) are seeded
here and used by render_tool_guidance.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy import and_, desc, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import AgentToolGuide, AgentToolGuideCandidate, AgentToolGuideVersion

logger = logging.getLogger("v2.agent").getChild("tool_guidance")

# ── Error Classification ───────────────────────────────────────────

ERROR_CLASSES = [
    "tool_not_found",
    "permission_denied",
    "path_denied",
    "network_error",
    "timeout",
    "syntax_error",
    "model_bad_arguments",
    "empty_output",
    "partial_output",
    "needs_browser",
    "needs_publish",
    "rate_limited",
    "unknown",
]


def classify_error(tool_result: dict, exception: str = "") -> str:
    """Classify a tool error into one of the ERROR_CLASSES.

    Inspects tool result envelope, stderr, and exception string.
    """
    error = tool_result.get("error") or exception or ""
    error_lower = error.lower()

    if not error:
        stderr = tool_result.get("stderr", "")
        stdout = tool_result.get("stdout", "")
        if stderr and not stdout:
            return "partial_output"
        return "empty_output"

    if "not found" in error_lower and ("tool" in error_lower or "command" in error_lower):
        return "tool_not_found"
    if "permission" in error_lower or "denied" in error_lower or "forbidden" in error_lower:
        return "permission_denied"
    if "path" in error_lower and ("denied" in error_lower or "invalid" in error_lower):
        return "path_denied"
    if "network" in error_lower or "connection" in error_lower or "dns" in error_lower:
        return "network_error"
    if "timeout" in error_lower or "timed out" in error_lower:
        return "timeout"
    if "syntax" in error_lower or "parse" in error_lower or "compile" in error_lower:
        return "syntax_error"
    if "argument" in error_lower or "parameter" in error_lower or "badarg" in error_lower:
        return "model_bad_arguments"
    if "rate" in error_lower or "limit" in error_lower or "throttle" in error_lower:
        return "rate_limited"
    if "browser" in error_lower or "js" in error_lower or "javascript" in error_lower:
        return "needs_browser"
    if "publish" in error_lower or "desktop" in error_lower:
        return "needs_publish"
    return "unknown"


# ── Degradation Recipes (Task B) ───────────────────────────────────

DEGRADATION_RECIPES: list[dict] = [
    {
        "id": "recipe_artifact_workflow",
        "title": "文件操作走制品生命周期",
        "trigger": (
            "Agent 试图直接生成同名 Office 文件、手动 base64 编码二进制、"
            "遇到同名文件冲突、或不知道该用哪个工具链操作文件"
        ),
        "error_classes": ["model_bad_arguments", "needs_publish"],
        "steps": [
            "1. 优先使用 Content Package 生命周期：content:pipeline(file_id) → content:get_full_package → content:update_blocks → content:export/publish",
            "2. content:export 支持 auto_rename/create_version/overwrite 三种冲突策略，不会因同名卡死",
            "3. 需要新建 Office 文件：office-gen:generate_to_artifact（自动创建 Content Package 和 artifact）",
            "4. 二进制替换：desktop-tools:replace_file(source_artifact_id=...) 不用 base64",
            "5. 同名冲突：使用 conflict_policy='create_version' 保留旧版本",
            "6. 验收：content:get_full_package 可读回 blocks，content:export 可重新导出文件",
        ],
        "acceptance": "文件在桌面列表中可见且内容正确，旧版本可通过 list_versions 查看",
    },
    {
        "id": "recipe_publish_to_desktop",
        "title": "工作区成果上桌面",
        "trigger": "用户意图含 '保存到桌面'/'给我文件'/'放到桌面' 或工具产生草稿后未 publish",
        "error_classes": ["needs_publish", "empty_output"],
        "steps": [
            "1. 确认工作区已生成成果文件",
            "2. 调用 terminal-tools:publish 将文件发布到框架文件系统",
            "3. 验收：调用 desktop-tools 或其等价 read-back 校验文件存在且内容正确",
        ],
        "acceptance": "桌面文件列表或文件详情能读回，内容与草稿一致",
    },
    {
        "id": "recipe_git_clone_fallback",
        "title": "git clone 失败 → tarball/zip",
        "trigger": "git clone 命令返回 network_error / timeout / 认证失败",
        "error_classes": ["network_error", "timeout", "permission_denied"],
        "steps": [
            "1. 识别 clone URL (GitHub/GitLab 等)",
            "2. 尝试 release/source zip/tarball 下载",
            "3. 解压到工作区",
            "4. 验收：目录存在且关键文件（README/package.json）可读",
        ],
        "acceptance": "目录存在且关键文件可读",
    },
    {
        "id": "recipe_syntax_fallback",
        "title": "Python/shell 反复语法错误 → run_python/write_file",
        "trigger": "连续两次 heredoc/引号执行返回 syntax_error",
        "error_classes": ["syntax_error"],
        "steps": [
            "1. 检测连续语法错误次数（>=2 触发降级）",
            "2. 将代码写入工作区文件（write_file）",
            "3. 执行文件而非内联脚本",
            "4. 验收：脚本退出码、输出、产物文件",
        ],
        "acceptance": "脚本退出码 0，输出符合预期，产物文件存在",
    },
    {
        "id": "recipe_url_redirect_chain",
        "title": "短链/跳转链接解析 → HTTP 请求链路",
        "trigger": "短链/跳转 URL 返回 30x 或无法直接解析内容",
        "error_classes": ["network_error", "empty_output"],
        "steps": [
            "1. 发 HEAD/GET 请求，跟踪 30x 重定向",
            "2. 若普通 HTTP 无法获取 JS 渲染内容，启用 browser-tools",
            "3. 验收：得到最终长链、标题或页面正文",
        ],
        "acceptance": "获得最终目标 URL、页面标题或正文摘要",
    },
    {
        "id": "recipe_tool_discovery",
        "title": "工具找不到/参数不明 → skill_list/skill_describe",
        "trigger": "Agent 声称'没有能力'或工具返回 tool_not_found",
        "error_classes": ["tool_not_found", "model_bad_arguments"],
        "steps": [
            "1. 调用 skill_list 列出所有可用工具",
            "2. 用 skill_describe 查看候选工具的详细参数",
            "3. 选择匹配意图的工具并调用",
            "4. 验收：记录使用了哪个工具和为何选择",
        ],
        "acceptance": "确认找到并使用正确工具，记录选择理由",
    },
]


def match_degradation_recipe(error_class: str, user_input: str = "") -> dict | None:
    """Find the first degradation recipe matching the error class and input."""
    for recipe in DEGRADATION_RECIPES:
        if error_class in recipe["error_classes"]:
            return recipe
    return None


DEFAULT_TOOL_GUIDES: list[dict] = [
    {
        "agent_code": "default",
        "tool_name": "skill_list",
        "scope": "global",
        "title": "工具发现入口",
        "guide_text": (
            "当不确定当前任务该用哪个工具时，先调用 skill_list 查看可用能力。"
            "不要直接回答‘没有能力’；先按模块或关键词缩小候选，再进入 skill_describe。"
        ),
        "failure_policy": {"error_map": {"tool_not_found": ["重新调用 skill_list", "按模块名过滤候选"]}},
        "acceptance_policy": {"check": "返回候选工具名称和选择理由"},
    },
    {
        "agent_code": "default",
        "tool_name": "skill_describe",
        "scope": "global",
        "title": "工具参数确认",
        "guide_text": (
            "调用具体工具前，使用 skill_describe 查看参数、权限和工具指引。"
            "如果返回 tool_guidance，必须遵守其中的失败降级和验收规则。"
        ),
        "failure_policy": {"error_map": {"model_bad_arguments": ["重新读取 parameters", "补齐必填参数后再调用"]}},
        "acceptance_policy": {"check": "明确目标工具、必填参数和验收方式"},
    },
    {
        "agent_code": "default",
        "tool_name": "skill_use",
        "scope": "global",
        "title": "工具执行与验收",
        "guide_text": (
            "调用工具后必须检查 success/error/data，不得只看 HTTP 200。"
            "写入、下载、发布类操作完成后要读回或列出产物验证。"
        ),
        "failure_policy": {"error_map": {"unknown": ["分类错误原因", "按降级 recipe 选择替代路径"]}},
        "acceptance_policy": {"check": "工具结果成功且关键产物可读回"},
    },
    {
        "agent_code": "default",
        "tool_name": "content:*",
        "scope": "global",
        "title": "Content Package 结构化内容编辑（首选）",
        "guide_text": (
            "Content Package 是所有结构化内容的规范来源。"
            "编辑已有文档/表格/演示时，默认走 Content Package 生命周期：\n"
            "1. 解析文件：content:pipeline(file_id) 生成 Content Package。\n"
            "2. 查看内容：content:get_full_package(package_id) 读取所有 blocks。\n"
            "3. 列出块：content:list_blocks(package_id) 按类型/页过滤。\n"
            "4. 更新块：content:update_blocks(package_id, updates=[{block_id, text}])。\n"
            "5. 替换文本：content:replace_text(package_id, {old_text, new_text})。\n"
            "6. 追加块：content:append_blocks(package_id, blocks=[{type, text}])。\n"
            "7. 重新导出：content:export(package_id, target_format) 编译为物理文件。\n"
            "8. 发布为制品：content:publish(package_id) 进入 artifact 生命周期。\n"
            "9. 版本管理：content:list_versions / content:restore_version。"
        ),
        "failure_policy": {
            "error_map": {
                "tool_not_found": [
                    "确认 content 模块已加载",
                    "回退到 office-gen:generate_to_artifact 生成新文件",
                ],
                "permission_denied": [
                    "package 属于其他用户，无法操作",
                    "确认你有该 source file 的 owner 或 share 权限",
                ],
            }
        },
        "acceptance_policy": {"check": "content:get_full_package 可读回更新后的 blocks，content:export 可重新导出"},
    },
    {
        "agent_code": "default",
        "tool_name": "office-gen:*",
        "scope": "global",
        "title": "Office 文件生成（底层 adapter，编辑已有文件请用 content:*）",
        "guide_text": (
            "office-gen 是底层格式生成 adapter，用于新建 Office 文档。"
            "编辑已有文件时，请优先使用 content:* 系列能力：\n"
            "1. 新建文档：office-gen:generate_to_artifact 创建二进制和 Content Package。\n"
            "2. 编辑已有文件（推荐）：content:get_full_package → content:update_blocks → content:export。\n"
            "3. 替换已有文件内容：office-gen:replace_existing 直接替换 file_id 的二进制。\n"
            "4. 同名冲突策略：content:export 和 content:publish 支持 auto_rename/create_version/overwrite。\n"
            "5. 从已有文件导出为制品：office-gen:export_to_artifact。"
        ),
        "failure_policy": {
            "error_map": {
                "tool_not_found": [
                    "查看 office-gen 是否可用",
                    "降级为生成文本内容后用 desktop-tools:create_file",
                ],
                "model_bad_arguments": [
                    "检查 sheets/content/slides 参数结构",
                    "确认 filename 不含扩展名",
                ],
            }
        },
        "acceptance_policy": {"check": "Content Package 可读回且可导出，或文件存在于桌面文件列表"},
    },
    {
        "agent_code": "default",
        "tool_name": "excel-engine:*",
        "scope": "global",
        "title": "Excel 数据库工作簿编辑（特殊场景，非默认编辑路径）",
        "guide_text": (
            "excel-engine 是 UI 实时编辑器/特殊场景工具，不作为 Agent 默认结构化编辑入口。"
            "编辑已有 Excel 请优先走 content:* 路径：\n"
            "1. 首选：content:update_blocks / content:append_blocks 编辑 blocks → content:export。\n"
            "2. 特殊场景（数据库工作簿）：create_workbook → update_range/append_rows → export_xlsx。\n"
            "3. 导入已有文件为工作簿：import_file_to_workbook(file_id)。\n"
            "4. 更新桌面已有 Excel：content:export(package_id, target_format='xlsx')。\n"
            "5. Agent 不需要处理 xlsx 二进制，系统通过 Content Package 处理导出。"
        ),
        "failure_policy": {
            "error_map": {
                "model_bad_arguments": [
                    "检查 state_key 是否从 create_workbook/import_file_to_workbook 返回",
                    "rows 必须为二维数组",
                ],
                "tool_not_found": [
                    "确认 excel-engine 模块已加载",
                    "降级为使用 content:update_blocks + content:export",
                ],
            }
        },
        "acceptance_policy": {"check": "excel-engine 工作簿可通过 Content Package 导出验证，或直接 content:export 验证"},
    },
    {
        "agent_code": "default",
        "tool_name": "desktop-tools:*",
        "scope": "global",
        "title": "桌面文件操作规范",
        "guide_text": (
            "1. 完整 CRUD 可用：list_files / get_file / create_file / replace_file / delete_file / rename_file / copy_file。"
            "2. 二进制文件替换：使用 replace_file(source_artifact_id=artifact_id) 或 replace_file_from_artifact，不需要手动 base64。"
            "3. 产物发布：publish_artifact(artifact_id, target_file_id?) 将制品发布为桌面文件。"
            "4. 版本管理：list_versions(artifact_id) 查看历史版本，restore_version(artifact_id, version_id) 回退。"
            "5. 同名冲突：replace_file 支持 conflict_policy 参数（create_version / overwrite / fail / auto_rename），默认 create_version 保留旧版本。"
            "6. 删除是软删除，可通过恢复操作还原。"
        ),
        "failure_policy": {
            "error_map": {
                "permission_denied": [
                    "确认你有文件的 owner 或 share 权限",
                    "文件可能已被删除",
                ],
                "model_bad_arguments": [
                    "检查 source_artifact_id 是否正确",
                    "检查 target_file_id 是否存在",
                ],
            }
        },
        "acceptance_policy": {"check": "操作成功后文件在 desktop-tools:list_files 中可见，内容正确"},
    },
    {
        "agent_code": "default",
        "tool_name": "artifacts:*",
        "scope": "global",
        "title": "制品生命周期操作",
        "guide_text": (
            "1. Artifact 是统一的产物生命周期对象，支持 create / get / list / update / replace / delete / restore。"
            "2. 版本管理：create_artifact_version 创建快照，list_artifact_versions 查看，restore_artifact_version 回退。"
            "3. 导出发布：export_artifact 导出为文件，publish_artifact 发布到桌面。"
            "4. 存储模式：db（结构化内容存数据库）、file（物理文件）、hybrid（两者兼备）。"
            "5. 同名冲突策略：fail（报错）、overwrite（覆盖）、auto_rename（自动改名）、create_version（创建新版本，默认）。"
        ),
        "failure_policy": {
            "error_map": {
                "not_found": ["确认 artifact_id 存在且未被软删除"],
                "permission_denied": ["artifact 属于其他用户"],
            }
        },
        "acceptance_policy": {"check": "artifact 可检索，版本可查看，内容可导出"},
    },
]


async def ensure_default_tool_guides(db: AsyncSession) -> None:
    """Seed global meta-tool guides without overwriting edited content."""
    for seed in DEFAULT_TOOL_GUIDES:
        result = await db.execute(
            select(AgentToolGuide).where(
                and_(
                    AgentToolGuide.owner_id.is_(None),
                    AgentToolGuide.agent_code == seed["agent_code"],
                    AgentToolGuide.tool_name == seed["tool_name"],
                    AgentToolGuide.scope == seed["scope"],
                    AgentToolGuide.status == "active",
                )
            ).limit(1)
        )
        if result.scalar_one_or_none():
            continue
        db.add(AgentToolGuide(
            owner_id=None,
            agent_code=seed["agent_code"],
            tool_name=seed["tool_name"],
            scope=seed["scope"],
            version=1,
            title=seed["title"],
            guide_text=seed["guide_text"],
            failure_policy=seed["failure_policy"],
            acceptance_policy=seed["acceptance_policy"],
            enabled=True,
            status="active",
            source="seed",
        ))
    await db.commit()


# ── Tool Guidance CRUD ─────────────────────────────────────────────

SCOPE_ORDER = ["global", "enterprise", "role", "agent", "user", "session"]


def _scope_priority(scope: str) -> int:
    try:
        return SCOPE_ORDER.index(scope)
    except ValueError:
        return len(SCOPE_ORDER)  # unknown scope goes last


async def list_guides(
    db: AsyncSession,
    owner_id: int | None = None,
    agent_code: str | None = None,
    tool_name: str | None = None,
    scope: str | None = None,
    status: str | None = None,
) -> list[dict]:
    """List tool guides with optional filters."""
    stmt = select(AgentToolGuide)
    if owner_id is not None:
        stmt = stmt.where(AgentToolGuide.owner_id == owner_id)
    if agent_code:
        stmt = stmt.where(AgentToolGuide.agent_code == agent_code)
    if tool_name:
        stmt = stmt.where(AgentToolGuide.tool_name == tool_name)
    if scope:
        stmt = stmt.where(AgentToolGuide.scope == scope)
    if status:
        stmt = stmt.where(AgentToolGuide.status == status)
    stmt = stmt.order_by(desc(AgentToolGuide.updated_at))
    r = await db.execute(stmt)
    return [_guide_to_dict(g) for g in r.scalars().all()]


async def get_guide(db: AsyncSession, guide_id: int) -> dict | None:
    """Get a single tool guide by id."""
    r = await db.execute(select(AgentToolGuide).where(AgentToolGuide.id == guide_id))
    g = r.scalar_one_or_none()
    return _guide_to_dict(g) if g else None


async def propose_guide(
    db: AsyncSession,
    owner_id: int | None,
    agent_code: str,
    tool_name: str,
    scope: str,
    title: str,
    guide_text: str,
    failure_policy: dict | None = None,
    acceptance_policy: dict | None = None,
    source: str = "manual",
    proposed_by: int | None = None,
    source_trajectory_id: int | None = None,
) -> dict:
    """Submit a candidate guide for review (creates a Candidate record)."""
    candidate = AgentToolGuideCandidate(
        owner_id=owner_id,
        agent_code=agent_code,
        tool_name=tool_name,
        scope=scope,
        title=title,
        guide_text=guide_text,
        failure_policy=failure_policy or {},
        acceptance_policy=acceptance_policy or {},
        source=source,
        proposed_by=proposed_by,
        source_trajectory_id=source_trajectory_id,
        status="draft",
    )
    db.add(candidate)
    await db.commit()
    await db.refresh(candidate)
    return _candidate_to_dict(candidate)


async def activate_guide(
    db: AsyncSession,
    guide_id: int,
    activated_by: int | None = None,
) -> dict | None:
    """Activate a tool guide (publish from candidate or re-enable existing).

    For candidates: promote to active guide.
    For disabled guides: re-enable.
    """
    # Try as candidate first
    r = await db.execute(
        select(AgentToolGuideCandidate).where(AgentToolGuideCandidate.id == guide_id)
    )
    candidate = r.scalar_one_or_none()
    if candidate:
        return await _promote_candidate(db, candidate, activated_by)

    # Try as existing guide
    r = await db.execute(
        select(AgentToolGuide).where(AgentToolGuide.id == guide_id)
    )
    guide = r.scalar_one_or_none()
    if not guide:
        return None

    guide.enabled = True
    guide.status = "active"
    guide.updated_by = activated_by
    guide.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(guide)
    return _guide_to_dict(guide)


async def disable_guide(
    db: AsyncSession,
    guide_id: int,
    disabled_by: int | None = None,
) -> dict | None:
    """Disable an active tool guide."""
    r = await db.execute(
        select(AgentToolGuide).where(AgentToolGuide.id == guide_id)
    )
    guide = r.scalar_one_or_none()
    if not guide:
        return None
    guide.enabled = False
    guide.status = "disabled"
    guide.updated_by = disabled_by
    await db.commit()
    await db.refresh(guide)
    return _guide_to_dict(guide)


async def rollback_guide(
    db: AsyncSession,
    guide_id: int,
    target_version: int,
    rolled_back_by: int | None = None,
) -> dict | None:
    """Roll back a tool guide to a previous version.

    Finds the version snapshot from agent_tool_guide_versions and
    restores its content as a new active version.
    """
    r = await db.execute(
        select(AgentToolGuide).where(AgentToolGuide.id == guide_id)
    )
    guide = r.scalar_one_or_none()
    if not guide:
        return None

    # Find the target version snapshot
    vr = await db.execute(
        select(AgentToolGuideVersion)
        .where(
            and_(
                AgentToolGuideVersion.guide_id == guide_id,
                AgentToolGuideVersion.version == target_version,
            )
        )
        .order_by(desc(AgentToolGuideVersion.version))
        .limit(1)
    )
    snapshot = vr.scalar_one_or_none()
    if not snapshot:
        return None

    # Archive current as version history
    db.add(AgentToolGuideVersion(
        guide_id=guide.id,
        owner_id=guide.owner_id,
        agent_code=guide.agent_code,
        tool_name=guide.tool_name,
        scope=guide.scope,
        version=guide.version,
        title=guide.title,
        guide_text=guide.guide_text,
        failure_policy=guide.failure_policy,
        acceptance_policy=guide.acceptance_policy,
        status=guide.status,
        source="rollback",
    ))

    # Restore snapshot content
    guide.version += 1
    guide.title = snapshot.title
    guide.guide_text = snapshot.guide_text
    guide.failure_policy = snapshot.failure_policy
    guide.acceptance_policy = snapshot.acceptance_policy
    guide.source = "rollback"
    guide.updated_by = rolled_back_by
    guide.status = "active"
    guide.enabled = True
    await db.commit()
    await db.refresh(guide)
    return _guide_to_dict(guide)


async def _promote_candidate(
    db: AsyncSession,
    candidate: AgentToolGuideCandidate,
    promoted_by: int | None = None,
) -> dict:
    """Promote a candidate to active guide (admin approval)."""
    existing_scope = candidate.scope
    if existing_scope == "session":
        existing_scope = "user"

    # Check uniqueness: same (owner_id, agent_code, tool_name, scope) can
    # only have one active. Deactivate existing active ones.
    r = await db.execute(
        select(AgentToolGuide).where(
            and_(
                AgentToolGuide.owner_id == candidate.owner_id,
                AgentToolGuide.agent_code == candidate.agent_code,
                AgentToolGuide.tool_name == candidate.tool_name,
                AgentToolGuide.scope == existing_scope,
                AgentToolGuide.status == "active",
            )
        )
    )
    for existing in r.scalars().all():
        existing.status = "superseded"
        existing.enabled = False

    guide = AgentToolGuide(
        owner_id=candidate.owner_id,
        agent_code=candidate.agent_code,
        tool_name=candidate.tool_name,
        scope=existing_scope,
        version=1,
        title=candidate.title,
        guide_text=candidate.guide_text,
        failure_policy=candidate.failure_policy,
        acceptance_policy=candidate.acceptance_policy,
        enabled=True,
        status="active",
        source=candidate.source,
        created_by=candidate.proposed_by,
        updated_by=promoted_by,
    )
    db.add(guide)
    await db.commit()
    await db.refresh(guide)

    candidate.status = "promoted"
    candidate.reviewed_by = promoted_by
    candidate.promoted_guide_id = guide.id
    candidate.promoted_at = datetime.now(timezone.utc)
    await db.commit()

    return _guide_to_dict(guide)


# ── Render / Merge (Runtime Injection) ─────────────────────────────


async def render_tool_guidance(
    db: AsyncSession,
    owner_id: int,
    agent_code: str,
    tool_names: list[str],
    max_tokens: int = 2048,
) -> str:
    """Render merged guidance for the given tools.

    Merge order: global → enterprise → role → agent → user → session.
    Only returns guidance for the specified tool_names. Higher scopes add
    guidance after lower scopes; they never replace the global safety contract.
    """
    if not tool_names:
        return ""

    await ensure_default_tool_guides(db)

    stmt = select(AgentToolGuide).where(
        and_(
            AgentToolGuide.tool_name.in_(tool_names),
            AgentToolGuide.enabled,
            AgentToolGuide.status == "active",
            or_(AgentToolGuide.agent_code == agent_code, AgentToolGuide.agent_code == "default"),
        )
    )
    r = await db.execute(stmt)
    all_matches = r.scalars().all()

    if not all_matches:
        return ""

    visible = []
    for guide in all_matches:
        if guide.owner_id is None:
            visible.append(guide)
        elif guide.owner_id == owner_id:
            visible.append(guide)

    ordered = sorted(
        visible,
        key=lambda guide: (
            tool_names.index(guide.tool_name) if guide.tool_name in tool_names else len(tool_names),
            _scope_priority(guide.scope),
            0 if guide.agent_code == "default" else 1,
            guide.version or 0,
        ),
    )

    lines: list[str] = []
    estimated = 0
    for guide in ordered:
        header = f"## {guide.tool_name} [{guide.scope}/{guide.agent_code}]"
        if guide.title:
            header += f": {guide.title}"
        block = f"{header}\n{guide.guide_text}\n"
        if guide.failure_policy:
            fp = guide.failure_policy
            error_map = fp.get("error_map", {})
            if error_map:
                block += "降级策略：\n"
                for ec, steps in error_map.items():
                    block += f"- {ec}: {'; '.join(steps) if isinstance(steps, list) else steps}\n"
        if guide.acceptance_policy:
            ap = guide.acceptance_policy
            if ap.get("check"):
                block += f"验收：{ap['check']}\n"
        block += "\n"
        estimated += len(block)
        if estimated > max_tokens * 4:
            lines.append("（工具指引超出 token 上限，已截断）")
            break
        lines.append(block)

    return "\n".join(lines)


# ── Recipe Injection ───────────────────────────────────────────────


def get_degradation_advice(error_class: str) -> str:
    """Return degradation advice text for the given error class."""
    recipe = match_degradation_recipe(error_class)
    if not recipe:
        return f"错误类型「{error_class}」无预设降级方案，请检查工具参数和调用方式。"
    steps = "\n".join(recipe["steps"])
    return f"## 降级方案：{recipe['title']}\n触发条件：{recipe['trigger']}\n步骤：\n{steps}\n验收：{recipe['acceptance']}"


# ── Internal Helpers ───────────────────────────────────────────────


def _guide_to_dict(g: AgentToolGuide) -> dict:
    return {
        "id": g.id,
        "owner_id": g.owner_id,
        "agent_code": g.agent_code,
        "tool_name": g.tool_name,
        "scope": g.scope,
        "version": g.version,
        "title": g.title,
        "guide_text": g.guide_text,
        "failure_policy": g.failure_policy,
        "acceptance_policy": g.acceptance_policy,
        "enabled": g.enabled,
        "status": g.status,
        "source": g.source,
        "created_by": g.created_by,
        "updated_by": g.updated_by,
        "created_at": g.created_at.isoformat() if g.created_at else None,
        "updated_at": g.updated_at.isoformat() if g.updated_at else None,
    }


def _candidate_to_dict(c: AgentToolGuideCandidate) -> dict:
    return {
        "id": c.id,
        "owner_id": c.owner_id,
        "agent_code": c.agent_code,
        "tool_name": c.tool_name,
        "scope": c.scope,
        "title": c.title,
        "guide_text": c.guide_text,
        "failure_policy": c.failure_policy,
        "acceptance_policy": c.acceptance_policy,
        "status": c.status,
        "source": c.source,
        "source_trajectory_id": c.source_trajectory_id,
        "proposed_by": c.proposed_by,
        "reviewed_by": c.reviewed_by,
        "review_note": c.review_note,
        "promoted_at": c.promoted_at.isoformat() if c.promoted_at else None,
        "promoted_guide_id": c.promoted_guide_id,
        "created_at": c.created_at.isoformat() if c.created_at else None,
        "updated_at": c.updated_at.isoformat() if c.updated_at else None,
    }
