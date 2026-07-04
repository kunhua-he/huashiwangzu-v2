# 执行信：Agent 工具调用默认账本与产物追踪收口

## 一句话目标

把 Agent 的真实工具调用、失败、验证、产物引用，从“只有部分 workflow 场景记录”推进到“普通 Agent 运行默认可追溯”。

本任务只允许在 `modules/agent/` 内收口，不碰框架 ContentPackage 发布、不碰 release gate、不碰 Knowledge 后端、不改 backend/app。

## 必读

```text
/Users/hekunhua/Documents/Agent/PHP/华世王镞_v2/AGENTS.md
/Users/hekunhua/Documents/Agent/PHP/华世王镞_v2/开发文档/README.md
/Users/hekunhua/Documents/Agent/PHP/华世王镞_v2/开发文档/03_模块开发文档/README.md
/Users/hekunhua/Documents/Agent/PHP/华世王镞_v2/modules/agent/README.md
/Users/hekunhua/Documents/Agent/PHP/华世王镞_v2/开发文档/项目记忆/agent-workflow-runtime-link-接入真实运行链路补强.md
/Users/hekunhua/Documents/Agent/PHP/华世王镞_v2/开发文档/流程能力审计报告-20260704.md
```

## 修改边界

只允许修改：

```text
modules/agent/backend/
modules/agent/frontend/
modules/agent/sandbox/
modules/agent/README.md
modules/agent/backend/tests/ 或 modules/agent/*test*.py
开发文档/项目记忆/
```

禁止修改：

```text
backend/app/
dev_toolkit/
modules/knowledge/
backend/app/services/content/
frontend/src/desktop/ 非 agent 专属文件
```

如果需要调用 Content/Knowledge，只能通过框架能力调用，不得 import 对方模块代码，不得直接读写对方表。

## 当前问题

已有 Agent workflow 账本能力，但不是所有真实 Agent 主链路默认记录。审计里看到：

```text
agent_messages = 0
agent_events = 0
agent_tool_calls = 0
agent_workflow_runs = 0
agent_workflow_artifacts = 0
```

判断不是单纯空表 bug，而是“默认工作路径没有稳定落账”。

## 目标 1：普通工具调用默认记录 tool_call

要求：

1. Agent 运行时每次 capability/tool 调用都要有可追溯记录。
2. 至少记录：

```text
tool/capability 名称
arguments 摘要或安全裁剪版本
started_at / completed_at
status: running/completed/failed
error/reason
result 摘要或安全裁剪版本
conversation_id/message_id/workflow_run_id/workflow_step_id 如果有
```

3. 如果当前 workflow_run 不存在，不要强行创建复杂 workflow；可以记录为 conversation/message scoped tool call，或者写入现有 lightweight ledger。
4. 不允许因为账本失败导致用户工具调用主流程失败；账本失败要 warning + fallback，但不能静默吞掉。

## 目标 2：失败和验证默认可见

要求：

1. tool/capability 返回 `success:false`、`error`、`status=failed/error` 时，必须记录 failure。
2. 对关键工具结果写 verification 摘要：

```text
pass/fail/unknown
reason
source: runtime/tool_result/manual
```

3. LLM 返回 error 但未抛异常时，也要记录 runtime failure，不得记成 no_side_effect pass。

## 目标 3：产物追踪先做引用，不做发布闭环

不要在本任务里实现 ContentPackage -> Artifact publish。那是后续批次。

本任务只做 Agent 侧引用追踪：

```text
如果工具结果里有 file_id/package_id/artifact_id/document_id/chunk_id/page/source_file_id
Agent ledger/message_meta/artifact_ref 里要保留这些 id
前端能显示“本次产物/引用证据”摘要
```

要求：

1. 不直接读 Knowledge/Content 表。
2. 只保存工具结果返回的 id/reference。
3. 前端展示可先做轻量：显示引用类型和 id，点击能力如果已有则跳转，没有则显示不可打开原因。

## 目标 4：前端最小可见

在 Agent 前端里增加或完善“工具/证据/产物追踪”显示，不需要大改 UI。

最低要求：

```text
用户能看到本次 Agent 调用了哪些工具
每个工具成功/失败状态可见
失败原因可见
如果产生 file_id/package_id/document_id 等引用，可见
```

## 验证

必须跑：

```bash
backend/.venv/bin/ruff check modules/agent/backend
backend/.venv/bin/python -m pytest modules/agent/sandbox/test_module.py
```

如果已有相关测试，补跑：

```bash
backend/.venv/bin/python -m pytest modules/agent/backend/test_workflow_runtime_link.py
backend/.venv/bin/python -m pytest modules/agent/backend/test_workflow_service.py
backend/.venv/bin/python -m pytest modules/agent/backend/test_workflow_api.py
```

按实际存在路径调整，但必须覆盖 Agent workflow/runtime 相关测试。

活系统验证至少包含：

```text
agent:list_workflows
一次最小 tool/capability 调用能产生或更新账本/追踪摘要
失败工具调用能记录 failure
```

## 验收标准

```text
改动只在 modules/agent/ 与 开发文档/项目记忆/
ruff pass
agent sandbox pass
workflow/runtime 相关测试 pass
普通工具调用有默认记录
失败工具调用有 failure 记录
工具结果中的 file/package/document 引用能被 Agent 侧保存/展示
不实现 ContentPackage publish，不改框架 release gate
```

## 交付

写入项目记忆：

```text
开发文档/项目记忆/Agent工具调用默认账本与产物追踪收口.md
```

并调用：

```text
finish_task(module_key="agent", ...)
memory_write(agent="codex-agent-default-ledger-r1")
mcp_feedback(agent="codex-agent-default-ledger-r1")
```

## 提示词

请读取并执行：‘/Users/hekunhua/Documents/Agent/PHP/华世王镞_v2/开发文档/项目记忆/执行信-Agent工具调用默认账本与产物追踪收口.md’
