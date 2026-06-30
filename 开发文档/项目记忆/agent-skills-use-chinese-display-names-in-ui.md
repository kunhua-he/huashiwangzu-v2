---
name: "Agent skills use Chinese display names in UI"
type: task
tags: ["agent", "skills", "display-name", "frontend", "tool-ui", "media-asr", "docs-open"]
created: 2026-06-30
agent: codex
---

Implemented Chinese display names for Agent skills without changing internal tool IDs. `skill_list` now returns `display_name` (user-facing Chinese name) alongside `name` (internal skill_use ID), and `skill_describe` includes `display_name`. Agent prompt seed and meta-tool descriptions were adjusted to tell the model to show `display_name` to users and reserve `name` for calls. Agent frontend `ToolCallCard` now maps common internal tool names (`docs-open__open`, `media-asr__transcribe_video`, etc.) to Chinese labels while preserving the internal name in the title tooltip. Verification: ruff passed touched backend files, `modules/agent/backend` tests passed 223/223, frontend build passed, no forbidden `any` usage in ToolCallCard.
