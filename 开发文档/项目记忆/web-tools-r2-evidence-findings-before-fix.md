---
name: "web-tools r2 evidence findings before fix"
type: "task"
tags: [web-tools, r2, evidence, fake-success, sandbox, proxy]
agent: "codex-web-tools-followup-sweep-20260703-r2"
created: "2026-07-03T08:06:32.739710+00:00"
---

Evidence checkpoint after docs + codegraph/code_node/code_impact/routes/capabilities/db_schema. web-tools has two registered capabilities and matching HTTP routes: search/fetch. No module DB tables. Router impact is isolated to modules/web-tools/backend/router.py. Findings before fix: (1) fetch always configures the hardcoded default local proxy http://127.0.0.1:4780 when WEB_TOOLS_PROXY is unset and does not fall back direct, making networking depend on a local proxy; (2) sandbox/test_module.py only tests duplicated contract helpers and sample shapes, explicitly says no real web requests, and does not import/test production router; (3) HTML fetch can return success with empty extracted text if body text is empty after filtering; (4) search can return success with an empty result list after provider rows are filtered to no usable URLs, hiding all-invalid provider output. Manifest capabilities match runtime registration; no module tables; no hardcoded API keys found.
