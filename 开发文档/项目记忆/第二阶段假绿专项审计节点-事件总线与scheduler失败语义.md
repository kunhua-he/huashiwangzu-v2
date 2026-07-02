---
name: "第二阶段假绿专项审计节点-事件总线与Scheduler失败语义"
type: "task"
tags: [audit, false-green, event-bus, scheduler, content, sandbox, 20260702]
agent: "codex-conductor"
created: "2026-07-02T14:36:20.185163+00:00"
---

## 节点来源

假绿/吞错专项 explorer 返回，只读未改代码。主会话决定将其中完整链路问题纳入当前维修批。

## P1 完整链路问题

1. 事件总线把 handler 返回的失败语义记成 success：
   - `backend/app/services/event_bus.py` 当前只要 handler 不抛异常就当成功。
   - 重试路径也把返回值包装成成功。
   - 影响链路：`file.uploaded -> content pipeline/event handler -> event_log completed`，内部返回 `{success:false}` / `{status:failed}` / `{error:...}` 时不重试、不可观测。
   - 计划修复：抽统一 `_handler_result_is_failure`，对 `success:false`、`status in failed/error`、`error` 且非显式 success 的结果判失败；更新 emit/retry 路径；补 event_bus 单测。

2. Scheduler 到点执行 Agent 失败仍返回 success：
   - `modules/scheduler/backend/router.py` 定时执行捕获 Agent 异常后写 `execute_result`，最终返回 `success:true`。
   - worker 会把 scheduled_agent_job 记 completed，不会重试。
   - 计划修复：Agent 执行失败返回 `success:false/status:failed/error`；权限/身份解析失败不返回成功空列表。

3. Content lazy parse 假成功：
   - `backend/app/routers/content.py` 的 `content:get_file_content` lazy pipeline 异常后返回 `success:true` + 空 blocks + `status:parse_failed`。
   - 调用方只看 envelope 会把解析失败当空内容。
   - 计划修复：改为外层失败语义或抛业务异常，补测试。

## P2/Pending

- Knowledge re-chunk 无 chunk 返回 `ApiResponse(data={error})`，应改为统一失败。
- Excel 前端乐观更新 catch 空块，失败不回滚本地状态。
- browser-tools/web-tools/scheduler sandbox 测试吞掉自己制造的 AssertionError，导致测试假绿。

## 当前策略

主会话先修完整底层链路：event_bus、scheduler、content lazy parse。P2 在当前批若改动面小则顺手修；否则落下一节点。每个修复配 focused tests 和 ruff。
