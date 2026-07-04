# 执行信：模块 README 与 Sandbox 矩阵批量补齐

## 任务定位

这封信专门处理文档矩阵与 sandbox 声明，尽量避开核心业务代码，适合与“全链路产品化落地总攻大信”并发。

## 目标

把 ReleaseGate 当前 README acceptance matrix debt 从“missing=28”大幅压低，最好清零；同时补齐每个模块 sandbox 状态声明，避免总攻大信被文档债拖慢。

## 当前基线

ReleaseGate 已知：

```text
README acceptance matrix: modules=35, missing=28, changed_missing=0
```

## 范围

主要修改：

```text
modules/*/README.md
modules/*/sandbox/test_module.py（只有确有必要且很小的 smoke 才新增）
开发文档/03_模块开发文档/README.md
```

尽量不要改：

```text
backend/app
frontend/src
dev_toolkit
```

除非只是为了读取或验证，不要动业务逻辑。

## 必做

1. 扫描全部 `modules/*/manifest.json` 和现有 README。
2. 对缺 README 或缺 Acceptance Matrix 的模块补最小矩阵。
3. 每个模块矩阵至少包含：
   - Manifest contract
   - Backend capability
   - Frontend entry
   - File access
   - Sandbox
   - Smoke
   - Known debt
4. background-service 模块必须写清楚：不应有可打开窗口，component_key 应为空或遵循契约。
5. 对没有后端/前端/sandbox 的模块，写 `SKIP + reason`，不要假 PASS。
6. 对 parser 模块统一写解析输入、输出、ContentPackage/IR 对接状态。
7. 对 desktop/tool 类模块写权限边界、文件访问边界、是否可见入口。
8. 更新 `开发文档/03_模块开发文档/README.md` 中的模块验收总口径，如果已有则补链接/说明。

## 最小矩阵模板

```markdown
## Acceptance Matrix

| Area | Status | Verification |
|---|---|---|
| Manifest contract | PASS/DEBT/SKIP | manifest.json checked |
| Backend capability | PASS/DEBT/SKIP | registered capability or skip reason |
| Frontend entry | PASS/DEBT/SKIP | component_key / background-service contract |
| File access | PASS/DEBT/SKIP | check_file_access if file_id is used |
| Sandbox | PASS/DEBT/SKIP | sandbox/test_module.py or reason |
| Smoke | PASS/DEBT/SKIP | probe/call_capability/manual |
| Known debt | text | concise debt |
```

## 验收

必须跑：

```text
mcp release_gate skip_ui=true mode=preflight
mcp module_sandbox_matrix check=false
```

如果改了 Python sandbox，再跑相关 pytest/ruff。

## 输出

写收口到：

```text
开发文档/项目记忆/模块README与Sandbox矩阵批量补齐收口.md
```

必须包含：补了哪些模块、哪些仍 SKIP、release_gate README missing 变化、剩余 debt。
