"""把框架开放的跨模块能力（技能）转成大模型 function calling 工具定义。
Agent 不硬编码任何模块工具——有什么技能就有什么工具。"""
from app.services.module_registry import list_capabilities  # 调用框架（允许）

# 工具名用 module__action（function name 不能含冒号）
SEP = "__"

# JSON Schema 类型归一化映射（模块注册的 capability 可能用非标准类型名）
_TYPE_NORMALIZE = {"int": "integer", "float": "number", "bool": "boolean", "str": "string", "dict": "object", "list": "array"}


def _normalize_schema_types(schema: dict) -> dict:
    """递归修正 JSON Schema 中的类型名（如 int→integer）。"""
    if not isinstance(schema, dict):
        return schema
    fixed = {}
    for key, value in schema.items():
        if key == "type" and isinstance(value, str) and value in _TYPE_NORMALIZE:
            fixed[key] = _TYPE_NORMALIZE[value]
        elif key == "properties" and isinstance(value, dict):
            fixed[key] = {k: _normalize_schema_types(v) for k, v in value.items()}
        elif key == "items" and isinstance(value, dict):
            fixed[key] = _normalize_schema_types(value)
        elif isinstance(value, dict):
            fixed[key] = _normalize_schema_types(value)
        elif isinstance(value, list):
            fixed[key] = [_normalize_schema_types(item) if isinstance(item, dict) else item for item in value]
        else:
            fixed[key] = value
    return fixed


def _normalize_parameters(parameters: dict | None) -> dict:
    """把框架能力参数说明转换为 function calling 可接受的 JSON Schema。"""
    if not parameters:
        return {"type": "object", "properties": {}}
    if parameters.get("type") == "object":
        return _normalize_schema_types(parameters)

    properties = {}
    for key, value in parameters.items():
        if isinstance(value, dict) and value.get("type"):
            properties[key] = value
        else:
            properties[key] = {"type": "string", "description": str(value)}
    return _normalize_schema_types({"type": "object", "properties": properties})


def build_tools(role: str) -> list[dict]:
    """按当前用户角色，列出可用技能并转成 OpenAI function calling 工具定义。"""
    tools = []
    for cap in list_capabilities(role=role):
        name = f"{cap['module']}{SEP}{cap['action']}"
        tools.append({
            "type": "function",
            "function": {
                "name": name,
                "description": cap.get("description") or f"{cap['module']} 的 {cap['action']} 能力",
                "parameters": _normalize_parameters(cap.get("parameters")),
            },
        })
    return tools


def parse_tool_name(name: str) -> tuple[str, str]:
    """module__action -> (module, action).  Uses rpartition so module
    names containing '__' still parse correctly."""
    module, sep, action = name.rpartition(SEP)
    if not sep:
        return name, ""
    return module, action
