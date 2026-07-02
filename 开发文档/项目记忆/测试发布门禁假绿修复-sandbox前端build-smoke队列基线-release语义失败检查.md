---
name: "测试发布门禁假绿修复-sandbox前端build-smoke队列基线-release语义失败检查"
type: "task"
tags: [test-gate, release-gate, false-green, sandbox, smoke, 20260702]
agent: "codex-test-release-gate-worker"
created: "2026-07-02T14:59:08.228075+00:00"
---

# 做了什么

- `dev_toolkit/module_sandbox_matrix.py` 的 `--check` 不再只跑 Python `sandbox/test_module.py`；有 `frontend_build_cmd` 的模块也会执行前端 build，backend/frontend 任一命令失败都会让该模块 fail。
- `modules/browser-tools/sandbox/test_module.py`、`modules/web-tools/sandbox/test_module.py`、`modules/scheduler/sandbox/test_module.py` 清掉 `try/except AssertionError` 吞掉自己制造失败的假绿写法，改成 `_assert_rejected()`。
- `dev_toolkit/smoke.py` 把任务队列 failed/pending 基线前移到业务步骤执行前，避免业务步骤新增失败被后采样吞进基线。
- `dev_toolkit/release_gate.py` 增加 completed-but-result-failed 语义检查：读取最近 completed task 的 `result`，识别 `success:false`、`status:failed/error`、无 success:true 的 error；只把 gate 期间新增的语义失败 completed 判为 BLOCKER，历史存量判 DEBT。
- `audit_failed_count()` 改为 fail-closed，缺 `summary.failed` 直接报错，不再默认 0。

# 验证结果

- `ruff check` 本节点 9 个文件：通过。
- `pytest ../dev_toolkit/test_module_sandbox_matrix.py ../dev_toolkit/test_smoke_queue_gate.py ../dev_toolkit/test_release_gate.py`：20 passed。
- 三个 sandbox 脚本单跑：browser-tools/web-tools/scheduler 全部 PASS。
- `/api/health`：200，status ok，worker handler 已注册。
- `release_gate.py --skip-ui`：历史 failed 基线=896，gate-run failed delta=PASS（未新增），semantic failed completed=0；最终 BLOCKER 来自 Sandbox matrix。

# 新暴露的真实 blocker

`module_sandbox_matrix.py --check --json` 现在返回：34 modules / 16 pass / 13 fail / 5 skip。13 个 fail 全是前端 build 被纳入后暴露：desktop-tools、docx-parser、douyin-delivery、excel-engine、hello-world、image-vision、knowledge、pdf-parser、pptx-parser、terminal-tools、text-parser、wechat-writer、xlsx-parser。大多数是 sandbox 内 `vite: command not found`，knowledge 是前端 build 解析失败。后续要按模块补 sandbox 前端依赖/构建策略，而不是把门禁再放松。

# 关联 commit

尚未提交；当前 worktree 有多个其他 worker/main dirty 改动，本节点未回退。
