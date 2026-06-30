---
name: "Agent compaction upgrade and model gateway proxy isolation repair"
type: task
tags: ["agent", "context-compaction", "gateway", "proxy", "httpx", "commit-966be1b9", "commit-a0e507e9"]
created: 2026-06-30
agent: codex
---

2026-06-30 Codex continued the Agent context compaction and model gateway repair batch. Committed `966be1b9 fix(agent): upgrade context compaction reduction` for deterministic tool-result reduction, structured compaction summaries, budget-driven folding, DB-backed trigger policy tests, and new reducer tests. Committed `a0e507e9 fix(gateway): isolate model http clients from env proxy` after root-causing `Invalid port ':1'` to process-inherited HTTP_PROXY/NO_PROXY (`::1`) handling in httpx; added `trust_env=False` to model gateway, embedding/rerank, and watchdog httpx clients. Verification: restarted backend on 33000; `/api/gateway/health` returned opencode=true, llama=true, local=true; `/api/gateway/chat` returned OK; `/api/gateway/embedding` and `/api/gateway/rerank` returned success; `/api/agent/chat` conversation 114 returned SSE assistant OK with usage; ruff passed on touched Python files; tests passed: 49 compaction/reducer tests and 16 async compaction tests. Mimo and Ollama health stayed false, unrelated to this fix.
