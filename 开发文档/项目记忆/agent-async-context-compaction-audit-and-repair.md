---
name: "Agent async context compaction audit and repair"
type: task
tags: ["agent", "context", "compaction", "latency", "async", "commit-19d50cb1"]
created: 2026-06-30
agent: codex
---

Audited commit 23a33bf and repaired the Agent asynchronous context compaction chain in commit 19d50cb1. Fixed the real worker TypeError from folded_count/int, prevented background compression from writing legacy compaction events, made ready publication conditional and race-safe across duplicate workers and concurrent edit/rollback/delete, selected compactions by highest watermark, preserved tool call/result groups, included tool payloads in summaries, reapplied tool-result reduction after projection, removed Stage 5 blind message slicing, and made legacy compaction events audit-only so raw fallback remains raw. Verified 179 Agent tests and 452 backend tests, live E2E 24/24, health handler registration, and long conversation 101 context assembly at 91ms versus the previous logged 26.7s pre-stream path.
