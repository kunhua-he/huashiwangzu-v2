---
name: "底层深度维修 checkpoint：网关降级、知识库生命周期、假绿治理、工具台 MCP"
type: "task"
tags: [checkpoint, repair, gateway, knowledge, fake-success, dev-toolkit, 20260702]
agent: "codex-conductor"
created: "2026-07-02T16:11:01.614547+00:00"
---

主会话 checkpoint：在多代理并行审计基础上，已稳定验证并准备提交推送一批底层维修。

关键修复：
- 模型网关：云端 5xx/quota/key 错进入 profile fallback，保留云端底座，优先 gemma-4 llama.cpp，再 ollama-local，最后 deepseek-v4-pro；本地模型启动前校验 llama.cpp 二进制与 model_path/mmproj_path，失败 diagnostics 稳定。
- 知识库：pipeline 生命周期债 dry-run/apply 闭环；source missing/deleted 归档时同步文档 parse_error；doc missing/doc deleted 标 obsolete；parser no content 改为 degraded 软失败并允许深层 raw/fusion 继续，保留诊断。
- 假绿：image-gen provider 成功但无可用图片不再 success+empty；历史查询异常不再空列表假成功。
- 工具台 MCP：server.py 组件化注册、mcp_entry/.mcp.json 标准入口、db_reverse_audit、release_gate、sandbox 矩阵增强。
- sandbox：34 个模块 sandbox backend/frontend 自动验收全部 pass。

验证：
- gateway + protocol + adapters + tool call accumulator + knowledge lifecycle/prompt + fake-success/event/scheduler/agent focused tests：81 passed。
- knowledge ingest status tests：8 passed。
- dev_toolkit focused tests：60 passed。
- ruff focused：All checks passed。
- git diff --check：干净。
- release_gate --skip-ui：PASS_WITH_DEBT；无 BLOCKER；failed 899 -> 899 无新增；recent failed 0；semantic failed completed 0；sandbox 34 pass/0 skip。

残留：历史队列 failed=899 属历史债，仍为 tracked debt；UI Playwright 本次按 --skip-ui 跳过。多个新子代理因本地 responses 502 中断，非项目代码结论。
