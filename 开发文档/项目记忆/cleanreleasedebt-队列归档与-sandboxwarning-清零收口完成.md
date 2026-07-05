---
name: "CleanReleaseDebt 队列归档与 SandboxWarning 清零收口完成"
type: "task"
tags: [release-gate, queue, sandbox, ui-e2e, knowledge-lifecycle]
agent: "codex"
created: "2026-07-05T09:39:33.892826+00:00"
---

完成 CleanReleaseDebt 队列归档与 SandboxWarning 清零收口：smoke/release gate 以 active_failed 判定队列阻断，deleted-source obsolete 通过 governance 显式 task_ids 归档；sandbox matrix 35 pass/0 fail/0 skip，19 个 chunk warning 归为 INFO 非 blocker。期间稳定了 UI gate 的 admin token 复用与桌面恢复，并让 content artifact 测试 cleanup 先软删自身知识文档，避免 source_missing lifecycle debt。最终 full release gate PASS，clean_release_ready=true；gate 后 live queue failed=0 active_failed=0 pending=0，knowledge lifecycle matched=0。关键提交：a20a88b6, 69afdd01, 63c8a315, 6d19329e, ff1faba8, d8051f73。
