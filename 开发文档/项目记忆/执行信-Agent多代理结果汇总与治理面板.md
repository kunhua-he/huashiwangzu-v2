# 执行信：Agent 多代理结果汇总与治理面板

## 目标

把多子代理执行结果从“散落日志/记忆”收口成 Agent 内可见的汇总面板：谁在做、做完什么、失败什么、产物/证据是什么、还能继续什么。

## 修改边界

只允许：

```text
modules/agent/backend/
modules/agent/frontend/
modules/agent/sandbox/
modules/agent/README.md
开发文档/项目记忆/
```

禁止：

```text
backend/app/
dev_toolkit/
modules/knowledge/
backend/app/services/content/
frontend/src/desktop/
```

## 必做

1. 在 Agent 内汇总 workflow/tool_call/artifact/failure/verification，形成“多代理执行摘要”。
2. 前端 Agent 面板展示：

```text
子代理/步骤
状态：running/completed/failed/blocked
完成摘要
失败原因
引用/产物 id
下一步建议
```

3. 支持空状态：没有多代理记录时不报错。
4. 不实现 ContentPackage publish，不碰框架 Artifact。
5. 只保存/展示已有 tool result references，不跨模块读表。

## 验收

必跑：

```bash
backend/.venv/bin/ruff check modules/agent/backend
backend/.venv/bin/python -m pytest modules/agent/sandbox/test_module.py
```

如存在则跑：

```bash
backend/.venv/bin/python -m pytest modules/agent/backend/test_workflow_runtime_link.py
backend/.venv/bin/python -m pytest modules/agent/backend/test_workflow_service.py
backend/.venv/bin/python -m pytest modules/agent/backend/test_workflow_api.py
```

前端：

```bash
cd frontend && npm run build
```

活栈：

```text
agent:list_workflows
agent workflow/tool_call/artifact/failure 样本可汇总
```

## 交付

写：

```text
开发文档/项目记忆/Agent多代理结果汇总与治理面板收口.md
```

调用：

```text
finish_task(module_key="agent", ...)
memory_write(agent="codex-agent-multi-summary-r1")
mcp_feedback(agent="codex-agent-multi-summary-r1")
```

## 提示词

请读取并执行：‘/Users/hekunhua/Documents/Agent/PHP/华世王镞_v2/开发文档/项目记忆/执行信-Agent多代理结果汇总与治理面板.md’
