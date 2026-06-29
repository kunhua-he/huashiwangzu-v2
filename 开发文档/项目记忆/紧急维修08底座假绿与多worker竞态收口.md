---
name: "紧急维修08底座假绿与多Worker竞态收口"
type: task
tags: ["维修", "多worker", "task-worker", "event-bus", "knowledge", "agent", "smoke", "health"]
created: 2026-06-29
agent: codex
---

执行紧急维修08收口。修复 task worker 多 worker 启动误回收 running 任务、handler 语义失败被误标 completed；event_bus 增加 processing lease、原子 retry 抢占、只重放失败 handler；knowledge 主链路恢复 parse/vector/search，并用 advisory lock 防同文件并发重复登记；agent JSON 状态改为 fcntl 文件锁保护完整 read-modify-write；health 从固定 ok 改为汇总 DB/module_errors/worker/event_bus/task_queue 状态；修复 dev_toolkit smoke/lint 分发与 smoke 假绿、desktop-tools capability drift、Playwright 中文登录选择器。验证：ruff 改动 Python 文件通过；backend pytest tests 446 passed；frontend npm run build 通过；capability drift OK；SMOKE_SKIP_UI=1 dev_toolkit/smoke.py 直接命令全绿；活系统 /api/health status=ok；id>3000 语义失败 completed 查询为空；Knowledge 真实 txt 链路 document_id=261/task_id=3048 parse/vector/chunk/search 通过。收尾清理：本轮 stability-audit 文档 255/257/259/260/261 与文件 360/362/364/366/368 已通过 API 软删。遗留：历史 kb_documents owner_id=4,file_id=218 重复阻挡唯一索引立即创建，应用层 advisory lock 已防未来重复；当前 MCP 连接仍可能是旧 dev_toolkit 进程，lint/smoke_all 工具分发需重连后生效。commit: 未提交。
