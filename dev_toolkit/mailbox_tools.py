"""Mailbox helpers for the project toolkit MCP server."""

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

MAILBOX_NAME = "华世王镞_v2邮箱"
TARGET_VALUES = ["opencode", "codex", "claude"]
CATEGORY_VALUES = ["业务模块", "框架任务", "维修", "审计修复", "调研", "探查", "平台健壮性", "桌面交互", "桌面视觉", "补修", "常驻"]
DELIVERY_MODE_VALUES = ["standard_bundle", "verification", "letter_only"]
DELIVERY_BUNDLE_FILES = ["交付报告.md", "修改文件清单.md", "验收命令结果.md", "剩余风险.md", "元信息.json"]
DECLARED_TOOL_NAMES = {"mailbox_write_letter", "mailbox_create_delivery_bundle", "mailbox_check_delivery_bundle"}
TOOL_NAMES = DECLARED_TOOL_NAMES | {"写封信"}

TASK_TYPE_MAP = {
    "业务模块": "开发（业务模块）",
    "框架任务": "开发（框架）",
    "维修": "修复",
    "审计修复": "修复（审计）",
    "调研": "调研",
    "探查": "探查（只读不写）",
    "平台健壮性": "开发（平台）",
    "桌面交互": "开发（桌面）",
    "桌面视觉": "开发（桌面）",
    "补修": "修复",
    "常驻": "规范",
}

CATEGORY_HINTS = {
    "业务模块": "业务模块开发任务，嵌入假桌面给同事用",
    "框架任务": "框架新增/改造任务",
    "维修": "紧急稳定性修复，按现象→根因→步骤执行",
    "审计修复": "修复性任务，按清单逐条修复",
    "调研": "纯调研，不改代码",
    "探查": "质量审计，只读不修改",
    "平台健壮性": "平台级健壮性提升",
    "桌面交互": "桌面交互功能开发",
    "桌面视觉": "桌面视觉效果开发",
    "补修": "遗留/收尾补修",
    "常驻": "常驻规范文档",
}

AGENT_HINT = {
    "opencode": "opencode（当前对话agent）",
    "codex": "Codex（CURSOR开发agent）",
    "claude": "Claude（其他agent）",
}


def tool_definitions() -> list[Any]:
    from mcp.types import Tool

    return [
        Tool(
            name="mailbox_write_letter",
            description="标准化写投递信到邮箱/投递箱/：自动补系统指令、必读文档、交付要求和收件箱路径。",
            inputSchema={
                "type": "object",
                "properties": {
                    "target": {
                        "type": "string",
                        "description": "目标 agent: opencode / codex / claude",
                        "enum": TARGET_VALUES,
                    },
                    "category": {
                        "type": "string",
                        "description": "信件分类",
                        "enum": CATEGORY_VALUES,
                    },
                    "title": {"type": "string", "description": "信件标题，不含 .md"},
                    "body": {"type": "string", "description": "信件正文 markdown"},
                    "note": {"type": "string", "description": "额外备注", "default": ""},
                    "required_docs": {"type": "string", "description": "额外必读文档，逗号或换行分隔", "default": ""},
                    "delivery_mode": {
                        "type": "string",
                        "description": "交付模式: standard_bundle / verification / letter_only",
                        "enum": DELIVERY_MODE_VALUES,
                        "default": "standard_bundle",
                    },
                    "overwrite": {"type": "boolean", "description": "同名信件存在时是否覆盖", "default": False},
                },
                "required": ["target", "category", "title", "body"],
            },
        ),
        Tool(
            name="mailbox_create_delivery_bundle",
            description="生成回信标准五件套到邮箱/收件箱/{任务名}/：交付报告、修改文件清单、验收命令结果、剩余风险、元信息.json。",
            inputSchema={
                "type": "object",
                "properties": {
                    "task_name": {"type": "string", "description": "收件箱任务目录名"},
                    "summary": {"type": "string", "description": "交付报告：做了什么"},
                    "changed_files": {"type": "string", "description": "修改文件清单，逗号或换行分隔"},
                    "verification_results": {"type": "string", "description": "验收命令和输出，原文粘贴"},
                    "risks": {"type": "string", "description": "剩余风险；无则写无", "default": "无"},
                    "key_design": {"type": "string", "description": "关键设计；无则空", "default": ""},
                    "data_stats": {"type": "string", "description": "数据统计；无则空", "default": ""},
                    "status": {"type": "string", "description": "任务状态", "default": "已完成"},
                    "self_test_passed": {"type": "boolean", "description": "自测是否通过", "default": True},
                    "max_file_lines": {"type": "number", "description": "最大文件行数", "default": 0},
                    "fix_count": {"type": "number", "description": "修复数", "default": 0},
                    "blocker_count": {"type": "number", "description": "卡点数", "default": 0},
                    "overwrite": {"type": "boolean", "description": "五件套已存在时是否覆盖", "default": False},
                },
                "required": ["task_name", "summary", "changed_files", "verification_results"],
            },
        ),
        Tool(
            name="mailbox_check_delivery_bundle",
            description="检查邮箱/收件箱/{任务名}/ 的标准五件套是否齐全，验证元信息.json 必填字段。",
            inputSchema={
                "type": "object",
                "properties": {
                    "task_name": {"type": "string", "description": "收件箱任务目录名"},
                },
                "required": ["task_name"],
            },
        ),
    ]


def handles_tool(name: str) -> bool:
    return name in TOOL_NAMES


async def handle_tool(repo_root: Path, name: str, arguments: dict[str, Any]) -> str:
    if name == "写封信":
        return await write_letter(
            repo_root,
            target=arguments["target"],
            category=arguments["category"],
            title=arguments["title"],
            body=arguments["body"],
            note=arguments.get("note", ""),
            delivery_mode="standard_bundle",
            overwrite=True,
        )
    if name == "mailbox_write_letter":
        return await write_letter(
            repo_root,
            target=arguments["target"],
            category=arguments["category"],
            title=arguments["title"],
            body=arguments["body"],
            note=arguments.get("note", ""),
            required_docs=arguments.get("required_docs", ""),
            delivery_mode=arguments.get("delivery_mode", "standard_bundle"),
            overwrite=bool(arguments.get("overwrite", False)),
        )
    if name == "mailbox_create_delivery_bundle":
        return await create_delivery_bundle(
            repo_root,
            task_name=arguments["task_name"],
            summary=arguments["summary"],
            changed_files=arguments["changed_files"],
            verification_results=arguments["verification_results"],
            risks=arguments.get("risks", "无"),
            key_design=arguments.get("key_design", ""),
            data_stats=arguments.get("data_stats", ""),
            status=arguments.get("status", "已完成"),
            self_test_passed=bool(arguments.get("self_test_passed", True)),
            max_file_lines=int(arguments.get("max_file_lines", 0)),
            fix_count=int(arguments.get("fix_count", 0)),
            blocker_count=int(arguments.get("blocker_count", 0)),
            overwrite=bool(arguments.get("overwrite", False)),
        )
    if name == "mailbox_check_delivery_bundle":
        return await check_delivery_bundle(repo_root, task_name=arguments["task_name"])
    raise ValueError(f"未知邮箱工具: {name}")


def mailbox_root(repo_root: Path) -> Path:
    return repo_root.parent / MAILBOX_NAME


def outbox_dir(repo_root: Path) -> Path:
    return mailbox_root(repo_root) / "投递箱"


def receive_dir(repo_root: Path) -> Path:
    return mailbox_root(repo_root) / "收件箱"


def system_instruction_path(repo_root: Path) -> Path:
    return mailbox_root(repo_root) / "_系统指令.md"


def make_letter_filename(category: str, title: str) -> str:
    safe_title = re.sub(r"[^\w\u4e00-\u9fff\-]", "", title.replace(" ", ""))
    prefix = category if category in ("调研", "探查", "补修", "常驻") else f"{category}-"
    return f"{prefix}{safe_title}.md"


def _safe_mailbox_name(name: str) -> str:
    cleaned = re.sub(r"[^\w\u4e00-\u9fff\-. ]+", "", name.strip()).strip(" .")
    if not cleaned:
        raise ValueError("名称不能为空")
    return cleaned[:120]


def _split_markdown_lines(raw: str) -> list[str]:
    return [item.strip() for item in re.split(r"[\n,]", raw or "") if item.strip()]


def _write_atomic_text(path: Path, content: str, *, overwrite: bool = True) -> bool:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and not overwrite:
        return False
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(content, encoding="utf-8")
    tmp.replace(path)
    return True


def _format_list_section(items: str, *, empty: str = "无") -> str:
    values = _split_markdown_lines(items)
    if not values:
        return empty
    return "\n".join(f"- {value}" for value in values)


def _delivery_bundle_dir(repo_root: Path, task_name: str) -> Path:
    return receive_dir(repo_root) / _safe_mailbox_name(task_name)


def _build_delivery_metadata(
    task_name: str,
    status: str,
    self_test_passed: bool,
    max_file_lines: int,
    fix_count: int,
    blocker_count: int,
) -> dict[str, Any]:
    return {
        "任务名": task_name,
        "状态": status,
        "自测通过": self_test_passed,
        "最大文件行数": max_file_lines,
        "修复数": fix_count,
        "卡点数": blocker_count,
        "提交时间": datetime.now(timezone.utc).isoformat(),
    }


async def write_letter(
    repo_root: Path,
    target: str,
    category: str,
    title: str,
    body: str,
    note: str = "",
    required_docs: str = "",
    delivery_mode: str = "standard_bundle",
    overwrite: bool = False,
) -> str:
    """Write a standardized task letter into the mailbox outbox."""
    filename = make_letter_filename(category, title)
    filepath = outbox_dir(repo_root) / filename
    if filepath.exists() and not overwrite:
        return json.dumps(
            {
                "success": False,
                "rejected": True,
                "error": "信件已存在；如需覆盖请传 overwrite=true",
                "path": str(filepath),
            },
            ensure_ascii=False,
            indent=2,
        )

    task_type = TASK_TYPE_MAP.get(category, "开发")
    hint = CATEGORY_HINTS.get(category, "")
    agent_label = AGENT_HINT.get(target, target)
    docs = [
        str(repo_root / "AGENTS.md"),
        str(repo_root / "开发文档" / "README.md"),
    ]
    docs.extend(_split_markdown_lines(required_docs))

    task_name = filename.removesuffix(".md")
    receive_path = receive_dir(repo_root) / task_name
    delivery_text = {
        "standard_bundle": (
            f"交付标准五件套 → `{receive_path}/`\n\n"
            "- `交付报告.md`\n"
            "- `修改文件清单.md`\n"
            "- `验收命令结果.md`\n"
            "- `剩余风险.md`\n"
            "- `元信息.json`\n"
        ),
        "verification": (
            f"验证类精简交付 → `{receive_path}/`\n\n"
            "- `验证报告.md`\n"
            "- `验收SQL结果.md`（如无 SQL，写明无）\n"
        ),
        "letter_only": "本信只需执行任务；如需回信，按任务正文要求写入收件箱。\n",
    }.get(delivery_mode, "本信使用标准五件套交付。\n")

    content = f"""# {task_name}

先读：{system_instruction_path(repo_root)}
类型：{task_type}
"""
    if hint:
        content += f"说明：{hint}\n"
    content += f"目标 agent：{agent_label}\n"
    if note:
        content += f"备注：{note}\n"
    content += "必读文档：\n"
    content += "".join(f"- {doc}\n" for doc in docs)
    content += "\n"
    content += body.strip()
    content += "\n\n## 交付要求\n\n"
    content += delivery_text
    content += "\n---\n"
    content += "> 本信由 MCP `mailbox_write_letter` 工具自动生成；旧别名：`写封信`。\n"

    _write_atomic_text(filepath, content, overwrite=True)
    return json.dumps(
        {
            "success": True,
            "path": str(filepath),
            "filename": filename,
            "task_name": task_name,
            "delivery_dir": str(receive_path),
            "prompt": f"请读取并执行：{filepath}",
            "content_preview": content[:800],
        },
        ensure_ascii=False,
        indent=2,
    )


async def create_delivery_bundle(
    repo_root: Path,
    task_name: str,
    summary: str,
    changed_files: str,
    verification_results: str,
    risks: str = "无",
    key_design: str = "",
    data_stats: str = "",
    status: str = "已完成",
    self_test_passed: bool = True,
    max_file_lines: int = 0,
    fix_count: int = 0,
    blocker_count: int = 0,
    overwrite: bool = False,
) -> str:
    """Create the standardized five-file delivery bundle under mailbox inbox."""
    safe_task_name = _safe_mailbox_name(task_name)
    target_dir = _delivery_bundle_dir(repo_root, safe_task_name)
    existing = [name for name in DELIVERY_BUNDLE_FILES if (target_dir / name).exists()]
    if existing and not overwrite:
        return json.dumps(
            {
                "success": False,
                "rejected": True,
                "error": "五件套文件已存在；如需覆盖请传 overwrite=true",
                "directory": str(target_dir),
                "existing_files": existing,
            },
            ensure_ascii=False,
            indent=2,
        )

    metadata = _build_delivery_metadata(
        safe_task_name,
        status=status,
        self_test_passed=self_test_passed,
        max_file_lines=max_file_lines,
        fix_count=fix_count,
        blocker_count=blocker_count,
    )
    files = {
        "交付报告.md": f"""# 交付报告

## 任务

{safe_task_name}

## 做了什么

{summary.strip() or "未填写"}

## 关键设计

{key_design.strip() or "无"}

## 数据统计

{data_stats.strip() or "无"}
""",
        "修改文件清单.md": f"""# 修改文件清单

{_format_list_section(changed_files, empty="无文件改动")}
""",
        "验收命令结果.md": f"""# 验收命令结果

{verification_results.strip() or "未填写"}
""",
        "剩余风险.md": f"""# 剩余风险

{risks.strip() or "无"}
""",
        "元信息.json": json.dumps(metadata, ensure_ascii=False, indent=2) + "\n",
    }

    written: list[str] = []
    for name, content in files.items():
        path = target_dir / name
        if _write_atomic_text(path, content, overwrite=True):
            written.append(str(path))

    return json.dumps(
        {
            "success": True,
            "directory": str(target_dir),
            "written_files": written,
            "metadata": metadata,
            "hint": "交付后可调用 mailbox_check_delivery_bundle(task_name) 检查五件套齐全性。",
        },
        ensure_ascii=False,
        indent=2,
    )


async def check_delivery_bundle(repo_root: Path, task_name: str) -> str:
    """Check whether a mailbox delivery bundle contains the required five files."""
    safe_task_name = _safe_mailbox_name(task_name)
    target_dir = _delivery_bundle_dir(repo_root, safe_task_name)
    files: list[dict[str, Any]] = []
    missing: list[str] = []
    errors: list[str] = []
    for name in DELIVERY_BUNDLE_FILES:
        path = target_dir / name
        if not path.exists():
            missing.append(name)
            continue
        item: dict[str, Any] = {
            "file": name,
            "path": str(path),
            "size_bytes": path.stat().st_size,
        }
        if name == "元信息.json":
            try:
                meta = json.loads(path.read_text(encoding="utf-8"))
                item["metadata_keys"] = sorted(meta.keys())
                required = {"任务名", "状态", "自测通过", "最大文件行数", "修复数", "卡点数", "提交时间"}
                missing_meta = sorted(required - set(meta.keys()))
                if missing_meta:
                    errors.append(f"元信息.json 缺少字段: {', '.join(missing_meta)}")
                    item["missing_metadata_keys"] = missing_meta
            except json.JSONDecodeError as exc:
                errors.append(f"元信息.json 不是合法 JSON: {exc}")
        files.append(item)

    return json.dumps(
        {
            "success": not missing and not errors,
            "directory": str(target_dir),
            "required_files": DELIVERY_BUNDLE_FILES,
            "files": files,
            "missing": missing,
            "errors": errors,
        },
        ensure_ascii=False,
        indent=2,
    )
