---
name: "LLM慢调用诊断工具与进度修正"
type: task
tags: ["gateway", "diagnostics", "knowledge", "progress", "llm"]
created: 2026-06-26
agent: opencode
---

完成了4件事：
1. Gateway diagnostics增强(trace_id/attempts/elapsed_ms/size/tokens) + JSONL持久化 + 查询端点
2. MCP工具增强(llm_probe/gateway_trace/task_trace/log_errors增强)
3. Knowledge progress不再pipeline未完成时显示done
4. 22次慢调用复现矩阵, 确认provider本身慢(avg 12.8s, 最高49s), gateway非瓶颈

改动的文件:
- backend/app/gateway/router.py (gateway diagnostics)
- backend/app/routers/gateway.py (traces endpoint)
- dev_toolkit/server.py (MCP tools)
- modules/knowledge/backend/services/progress_service.py (progress fix)

核心发现: provider(opencode deepseek-v4-flash)平均12.8秒, 最高49秒, 且91%一次成功无retry。
建议: provider侧优化(缓存/更快的模型通道/本地fallback)。
