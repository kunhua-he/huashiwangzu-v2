# ReleaseGate 二期能力漂移与文档矩阵门禁收口

时间：2026-07-04

执行 agent：codex-release-gate-contract-r1

## 目标

执行《执行信-ReleaseGate二期能力漂移与文档矩阵门禁.md》，确认 release gate 已覆盖发布契约门禁：

1. capability live registry vs manifest/source drift 进入 gate。
2. README 验收矩阵缺失进入 DEBT；新变更模块缺失可 BLOCKER。
3. normal app 空 component_key / background-service component_key 规则进入 gate。
4. frontend sandbox chunk warning 进入 DEBT。
5. 输出 compact summary：verdict、blockers、debts、clean_release_ready、deploy_allowed。

## 本轮变更

本轮未修改产品代码、模块代码或前后端运行时代码，只在允许边界内补充 release gate 测试覆盖：

- `dev_toolkit/test_release_gate.py`
  - 新增 `test_capability_drift_undeclared_live_is_blocker`。
  - 新增 `test_capability_drift_source_not_live_is_blocker`。
  - 新增 `test_component_key_contracts_blocks_missing_component_file`。

本轮确认现有实现已覆盖执行信要求的五类门禁：

- capability drift：manifest、live registry、source registered 三方差异进入 gate；`undeclared_live` / `source_not_live` 为 BLOCKER，`manifest_not_source` 为 DEBT。
- README acceptance matrix：缺失矩阵进入 DEBT，当前变更模块缺失可升级为 BLOCKER。
- component_key contracts：normal app 必须声明非空且存在的 component 文件；background-service 必须使用空 component_key。
- sandbox matrix：frontend sandbox chunk warning 已从 sandbox matrix 汇总进入 DEBT。
- compact summary：输出包含 `verdict`、`blockers`、`debts`、`clean_release_ready`、`deploy_allowed`。

## 验证结果

执行信指定验收命令：

```bash
backend/.venv/bin/ruff check dev_toolkit/release_gate.py dev_toolkit/release_response.py dev_toolkit/module_sandbox_matrix.py
```

结果：通过，`All checks passed!`

```bash
backend/.venv/bin/python -m pytest dev_toolkit/test_release_gate.py dev_toolkit/test_release_response.py
```

结果：通过，`40 passed, 1 skipped in 3.02s`

补充回归：

```bash
backend/.venv/bin/python -m pytest dev_toolkit/test_release_gate.py dev_toolkit/test_release_response.py dev_toolkit/test_module_sandbox_matrix.py
```

结果：通过，`58 passed, 1 skipped`

## 活栈 release_gate 结果

执行：

```text
release_gate(skip_ui=true, mode=preflight)
```

结果：`verdict=BLOCKER`，`success=false`，`clean_release_ready=false`，`deploy_allowed=false`。

该 BLOCKER 是门禁发现的真实存量契约问题，不在本执行信允许修改边界内，因此本轮只记录不修模块：

- `terminal-tools`：`background-service must use empty component_key`
- `web-tools`：`background-service must use empty component_key`

关键门禁结果：

- Capability drift：PASS，`manifest=186, live=186, source=186, missing_live=0, undeclared_live=0, source_not_live=0, manifest_not_source=0`
- README acceptance matrix：DEBT，`modules=35, missing=28, changed_missing=0`
- Component key contracts：BLOCKER，`modules=35, issues=2`
- Sandbox matrix：DEBT，preflight 模式未运行完整 sandbox matrix
- Compact summary：已输出 `verdict`、`blockers`、`debts`、`clean_release_ready`、`deploy_allowed`

## 边界说明

执行信允许修改：

- `dev_toolkit/release_gate.py`
- `dev_toolkit/release_response.py`
- `dev_toolkit/module_sandbox_matrix.py`
- `dev_toolkit/test_release_gate.py`
- `dev_toolkit/test_release_response.py`
- `dev_toolkit/test_module_sandbox_matrix.py`
- `开发文档/项目记忆/`

本轮实际修改：

- `dev_toolkit/test_release_gate.py`
- `开发文档/项目记忆/ReleaseGate二期能力漂移与文档矩阵门禁收口.md`

未修改执行信禁止路径：

- `backend/app/`
- `frontend/src/`
- `modules/`

当前工作区中仍有上一轮 ContentPackage 任务留下的脏文件，视为本轮基线外历史变更：

- `backend/tests/test_content_artifact_publish.py`
- `开发文档/项目记忆/ContentPackage到Artifact发布闭环收口.md`
- `开发文档/项目记忆/contentpackage-到-artifact-发布闭环复验与权限负例补强.md`
- `开发文档/项目记忆/工具台反馈-20260704-123659-codex-content-artifact-publish-r1-执行-contentpackage-到-artifact-发布闭环复验.md`

## 后续建议

1. 单独开模块任务修复 `terminal-tools`、`web-tools` 的 background-service `component_key` 契约问题。
2. 单独开文档补齐任务，为缺失验收矩阵的 28 个模块补 README acceptance matrix。
3. 在 release 候选前运行 full gate，包含 UI coverage、smoke_all 和完整 sandbox matrix。
