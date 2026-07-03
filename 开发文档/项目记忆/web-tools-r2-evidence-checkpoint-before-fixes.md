---
name: "web-tools r2 evidence checkpoint before fixes"
type: "task"
tags: [web-tools, r2, evidence, boundary, ssrf, proxy, sandbox]
agent: "codex-web-tools-r2-sweep"
created: "2026-07-03T08:50:55.187802+00:00"
---

Evidence checkpoint before edits. Tools used: brief, plan_task(module_key=web-tools), worktree_guard(include_untracked=true), code_explore, code_node, code_impact, routes, capabilities, db_schema. Dirty baseline includes other agents' douyin/office/scheduler work and data/uploads; this agent will not touch them. Findings in modules/web-tools: manifest public_actions align with registered search/fetch capabilities; fetch delegates SSRF checks to backend app.core.url_safety.validate_safe_url, including scheme/userinfo/private/link-local/metadata/DNS fail-closed and redirect revalidation. Module-local issues to fix: fetch uses default local proxy without direct fallback, fetch does not set trust_env=False, HEAD response is not explicitly closed, sandbox tests do not exercise real router failure paths.
