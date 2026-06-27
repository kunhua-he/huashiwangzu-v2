#!/usr/bin/env python3
"""Check module manifest public_actions against runtime register_capability calls.

Runtime registration is the authority for cross-module calls. Manifest
``public_actions`` is discovery metadata, so it must not drift from the
registered action names or their minimum roles.
"""

from __future__ import annotations

import ast
import json
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULES_DIR = ROOT / "modules"


@dataclass(frozen=True)
class Capability:
    module: str
    action: str
    min_role: str
    path: Path
    line: int


def _literal_string(node: ast.AST, constants: dict[str, str]) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.Name):
        return constants.get(node.id)
    return None


def _module_constants(tree: ast.Module) -> dict[str, str]:
    constants: dict[str, str] = {}
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        if len(node.targets) != 1 or not isinstance(node.targets[0], ast.Name):
            continue
        value = _literal_string(node.value, {})
        if value is not None:
            constants[node.targets[0].id] = value
    return constants


def _tuple_capabilities(node: ast.Assign, path: Path) -> list[Capability]:
    """Parse the agent-style capabilities = [(module, action, ..., min_role), ...]."""
    if len(node.targets) != 1 or not isinstance(node.targets[0], ast.Name):
        return []
    if node.targets[0].id != "capabilities" or not isinstance(node.value, ast.List):
        return []

    result: list[Capability] = []
    for item in node.value.elts:
        if not isinstance(item, ast.Tuple) or len(item.elts) < 7:
            continue
        module = _literal_string(item.elts[0], {})
        action = _literal_string(item.elts[1], {})
        min_role = _literal_string(item.elts[6], {}) or "viewer"
        if module and action:
            result.append(Capability(module, action, min_role, path, item.lineno))
    return result


def _registered_capabilities(path: Path) -> list[Capability]:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except SyntaxError as exc:
        raise RuntimeError(f"Cannot parse {path}: {exc}") from exc

    constants = _module_constants(tree)
    result: list[Capability] = []
    dynamic_sites: list[tuple[Path, int]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            result.extend(_tuple_capabilities(node, path))
            continue
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        func_name = ""
        if isinstance(func, ast.Name):
            func_name = func.id
        elif isinstance(func, ast.Attribute):
            func_name = func.attr
        if func_name != "register_capability":
            continue

        module = _literal_string(node.args[0], constants) if len(node.args) > 0 else None
        action = _literal_string(node.args[1], constants) if len(node.args) > 1 else None
        if not module or not action:
            dynamic_sites.append((path, node.lineno))
            continue
        min_role = "viewer"
        for keyword in node.keywords:
            if keyword.arg == "min_role":
                min_role = _literal_string(keyword.value, constants) or min_role
                break
        result.append(Capability(module, action, min_role, path, node.lineno))
    if dynamic_sites and not result:
        site_list = ", ".join(f"{p.relative_to(ROOT)}:{line}" for p, line in dynamic_sites)
        raise RuntimeError(f"Dynamic register_capability arguments are not checkable: {site_list}")
    return result


def _manifest_actions(manifest_path: Path) -> dict[str, str]:
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    actions: dict[str, str] = {}
    for item in data.get("public_actions") or []:
        if not isinstance(item, dict):
            continue
        action = item.get("action")
        if isinstance(action, str) and action:
            actions[action] = str(item.get("min_role") or "viewer")
    return actions


def main() -> int:
    manifest_actions: dict[str, dict[str, str]] = {}
    for manifest_path in sorted(MODULES_DIR.glob("*/manifest.json")):
        module = manifest_path.parent.name
        manifest_actions[module] = _manifest_actions(manifest_path)

    runtime_actions: dict[str, dict[str, Capability]] = {}
    for path in sorted(MODULES_DIR.glob("*/backend/**/*.py")):
        for capability in _registered_capabilities(path):
            if capability.module.startswith("_"):
                continue
            runtime_actions.setdefault(capability.module, {})[capability.action] = capability

    errors: list[str] = []
    for module in sorted(set(manifest_actions) | set(runtime_actions)):
        manifest = manifest_actions.get(module, {})
        runtime = runtime_actions.get(module, {})
        if not manifest and not runtime:
            continue

        manifest_only = sorted(set(manifest) - set(runtime))
        runtime_only = sorted(set(runtime) - set(manifest))
        if manifest_only:
            errors.append(f"{module}: manifest-only actions: {', '.join(manifest_only)}")
        if runtime_only:
            details = [
                f"{name} ({runtime[name].path.relative_to(ROOT)}:{runtime[name].line})"
                for name in runtime_only
            ]
            errors.append(f"{module}: runtime-only actions: {', '.join(details)}")

        for action in sorted(set(manifest) & set(runtime)):
            runtime_role = runtime[action].min_role
            manifest_role = manifest[action]
            if manifest_role != runtime_role:
                errors.append(
                    f"{module}:{action}: min_role mismatch "
                    f"manifest={manifest_role} runtime={runtime_role} "
                    f"({runtime[action].path.relative_to(ROOT)}:{runtime[action].line})"
                )

    if errors:
        print("[capability-drift] FAILED")
        for error in errors:
            print(f"  - {error}")
        return 1

    total = sum(len(actions) for actions in runtime_actions.values())
    print(f"[capability-drift] OK ({total} registered public capabilities)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
