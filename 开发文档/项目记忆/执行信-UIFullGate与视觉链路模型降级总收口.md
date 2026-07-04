# 执行信：UI Full Gate 与视觉链路模型降级总收口

## 任务定位

这封信处理当前剩余最明确的发布债：未跑完整 UI gate、视觉链路存在 mimo 401 / qwen3-vl context 过大观察项、skip-ui 导致 clean_release_ready=false。

目标是把“可部署 PASS_WITH_DEBT”推进到“UI/full gate 可解释、可复跑、失败项可归因”。

## 当前背景

已知：

```text
release_gate --skip-ui preflight: PASS_WITH_DEBT，无 blocker
deploy_allowed=true
clean_release_ready=false，因为 skip-ui/preflight/full-ui 未完整覆盖
视觉链路观察项：mimo 401 / qwen3-vl context 过大，当前降级后不是 blocker
```

## 总目标

1. 能运行 full gate（优先 skip_ui=false；如环境不支持，必须给出稳定降级和明确原因）。
2. Playwright/UI 测试失败必须可归因，不允许超时无上下文。
3. 视觉/模型链路要有 fallback，不因单模型 401 或 context too large 直接导致主链路失败。
4. release_gate 输出必须明确：
   - `release_safe`
   - `deploy_allowed`
   - `clean_release_ready`
   - UI coverage status
   - model fallback status

## 范围

```text
dev_toolkit/release_gate.py
dev_toolkit/smoke.py
dev_toolkit/test_release_gate.py
frontend/tests
frontend/src/shared/components/notification-panel.vue
frontend/src/shared/composables/use-notifications.ts
modules/image-vision/
modules/media-intelligence/
开发文档/项目记忆
```

## 必做需求

### A. UI Gate

1. 盘点现有 Playwright 测试，确认哪些能在常驻 5173 跑。
2. 禁止硬等；使用 storageState 与条件等待。
3. Full gate 跑 UI 时要输出 compact summary：通过数、失败数、失败测试、截图/trace 路径（如有）。
4. 如果 UI 环境不可用，要返回 DEBT，不应误判 PASS。
5. clean_release_ready 只有 full + UI + clean worktree + no blocker 时为 true。

### B. 视觉/模型链路

1. 对 mimo 401：识别为 auth/config debt，不能无限重试。
2. 对 qwen3-vl context 过大：要有压缩/截断/降级路径。
3. 前端/通知中心能展示模型降级：主模型失败、fallback 使用、最终是否成功。
4. 后端 smoke/release gate 能区分：模型不可用 blocker vs 有 fallback 的 debt。

### C. 测试

至少跑：

```text
npm --prefix frontend run build
相关 frontend Playwright 测试
pytest dev_toolkit/test_release_gate.py
pytest dev_toolkit/test_smoke_queue_gate.py
mcp release_gate skip_ui=false mode=full
```

若 `skip_ui=false` 因环境限制失败，必须再跑：

```text
mcp release_gate skip_ui=true mode=full
```

并解释差异。

## 输出

写收口到：

```text
开发文档/项目记忆/UIFullGate与视觉链路模型降级总收口.md
```

必须包含：full gate 结果、UI 失败归因、模型降级策略、clean_release_ready 判断、剩余 debt。
