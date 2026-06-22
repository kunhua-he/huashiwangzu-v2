"""Cross-module capability registration for terminal-tools.

All 8 capabilities are registered here at module load time.
"""

from __future__ import annotations

from app.services.module_registry import register_capability

from .exec import _exec
from .file_ops import _write_file, _read_file, _list_workspace, _publish, _import
from .python import _run_python, _chart

# ═══════════════════════════════════════════════════════════════════════
# Register capabilities with framework
# ═══════════════════════════════════════════════════════════════════════

register_capability(
    "terminal-tools",
    "exec",
    _exec,
    description="在用户工作区执行 shell 命令。受危险命令拦截、超时(默认60s)、输出1MB上限保护。cwd 锁定在用户工作区。返回 stdout/stderr/return_code。",
    brief="执行 shell 命令",
    parameters={
        "type": "object",
        "properties": {
            "command": {
                "type": "string",
                "description": "要执行的 shell 命令",
            },
            "timeout": {
                "type": "integer",
                "description": "超时秒数（默认 60s，最大 600s）",
                "default": 60,
            },
        },
        "required": ["command"],
    },
    min_role="editor",
)

register_capability(
    "terminal-tools",
    "write_file",
    _write_file,
    description="写文件到用户工作区。路径自动约束在工作区内，越界路径被拒绝。",
    brief="写文件到工作区",
    parameters={
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "工作区内的相对路径",
            },
            "content": {
                "type": "string",
                "description": "文件内容（UTF-8）",
            },
        },
        "required": ["path", "content"],
    },
    min_role="editor",
)

register_capability(
    "terminal-tools",
    "read_file",
    _read_file,
    description="读用户工作区内的文件内容。文本文件返回 UTF-8 内容，二进制文件返回大小信息。路径约束在工作区内。",
    brief="读取工作区文件",
    parameters={
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "工作区内的相对路径",
            },
        },
        "required": ["path"],
    },
    min_role="viewer",
)

register_capability(
    "terminal-tools",
    "list_workspace",
    _list_workspace,
    description="列出用户工作区内的文件和目录。目录优先，按名称排序。",
    brief="列出工作区文件",
    parameters={
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "工作区内的相对路径（默认根目录）",
                "default": ".",
            },
        },
    },
    min_role="viewer",
)

register_capability(
    "terminal-tools",
    "publish",
    _publish,
    description="将工作区文件显式交付到框架文件系统（桌面可见）。享受框架内容去重。返回框架文件 ID。",
    brief="文件发布到桌面",
    parameters={
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "工作区内的相对路径",
            },
            "filename": {
                "type": "string",
                "description": "交付后的显示名称（可选，默认用原文件名）",
            },
            "folder_id": {
                "type": "integer",
                "description": "目标文件夹 ID（可选，默认桌面根目录）",
            },
        },
        "required": ["path"],
    },
    min_role="editor",
)

register_capability(
    "terminal-tools",
    "import",
    _import,
    description="将框架文件系统的文件拷入工作区供 CLI 处理。owner 校验：只能 import 自己的文件。",
    brief="导入文件到工作区",
    parameters={
        "type": "object",
        "properties": {
            "file_id": {
                "type": "integer",
                "description": "框架文件 ID",
            },
            "target_path": {
                "type": "string",
                "description": "工作区内的目标相对路径（可选，默认用原文件名）",
            },
        },
        "required": ["file_id"],
    },
    min_role="editor",
)

register_capability(
    "terminal-tools",
    "run_python",
    _run_python,
    brief="运行 Python 代码",
    description=(
        "在用户工作区子进程执行 Python 数据分析代码。预置 pandas/numpy/matplotlib（Agg 后端）。"
        "代码用 plt.savefig() 存图、print() 输出文本。自动收集生成的图表文件并存入框架文件系统。"
        "input_files 传入 file_id 列表，框架自动备到工作区供代码读取。"
        "超时/输出截断复用 terminal-tools 保护。"
    ),
    parameters={
        "type": "object",
        "properties": {
            "code": {"type": "string", "description": "要执行的 Python 代码。可用 pandas/numpy/matplotlib（Agg 后端）。用 plt.savefig() 出图、print() 输出文本。"},
            "input_files": {"type": "array", "items": {"type": "integer"}, "description": "输入文件 file_id 列表（可选），备到工作区供代码读取"},
            "timeout": {"type": "integer", "description": "超时秒数（默认 60s，最大 600s）", "default": 60},
        },
        "required": ["code"],
    },
    min_role="editor",
)

register_capability(
    "terminal-tools",
    "chart",
    _chart,
    description="傻瓜式出图。传入数据数组和图表类型，后端用 matplotlib 直接出图存文件。支持折线(line)/柱状(bar)/饼图(pie)。",
    brief="自动生成图表",
    parameters={
        "type": "object",
        "properties": {
            "data": {"type": "array", "description": "数据数组，每个元素含 x/y 字段：[{x:'一月', y:100}, ...]"},
            "chart_type": {"type": "string", "enum": ["line", "bar", "pie"], "description": "line(折线)/bar(柱状)/pie(饼图)"},
            "title": {"type": "string", "description": "图表标题（可选）"},
            "x_label": {"type": "string", "description": "X 轴标签（可选）"},
            "y_label": {"type": "string", "description": "Y 轴标签（可选）"},
        },
        "required": ["data", "chart_type"],
    },
    min_role="editor",
)
