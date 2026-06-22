# Agent Module — AI Assistant

## Goal

Production-grade AI assistant for the V2 desktop shell. Multi-session, streaming, progressive tool discovery, engine-driven orchestration, three-layer prompt system, event-sourced conversation history, background task pool, sub-agent support, and auto-evolving user profiles. All business code and tables inside `modules/agent/`.

## Engine Subsystem (`modules/agent/engine/`)

The engine dir provides orchestration, resilience, and self-optimization:

| Module | Purpose |
|---|---|
| `engine.py` | Orchestration shell: assembles context, calls degradation chain, manages tool loops |
| `event_store.py` | Append-only event sourcing — records every model interaction as replayable events |
| `budget_allocator.py` | Dynamic token budget estimation, priority-based context assembly, safety cap |
| `compressor.py` | Context compression when token budget is exceeded (middle-truncation, hard tail trim) |
| `fallback_chain.py` | Full-chain degradation: primary → backup → cheap → echo, with stuck detector |
| `stuck_detector.py` | Detects repetitive loops (same tool call repeated) and triggers escalation |
| `layered_memory.py` | High-level memory integration (save/recall/fuse via memory module capabilities) |
| `experience_memory.py` | Success experience matching, saving, feedback (via memory:match/experience capabilities) |

## Progressive Tool Discovery

Instead of exposing every capability as a flat function list (which grows with module count), agent uses **3 meta-tools**:

| Tool | Purpose |
|---|---|
| `skill_list` | List all skills available to current role (name + one-line summary) |
| `skill_describe` | Get full description + parameters of a specific skill |
| `skill_use` | Invoke a skill by name with given parameters |

This keeps token footprint constant regardless of how many modules are added. The model first queries `skill_list` to see what's available, then calls `skill_describe` to understand parameters, then `skill_use` to execute.

## Background Task Pool

The module registers 4 task handlers with the framework worker (via `handlers/tasks.py`):

| Task Type | Handler | Purpose |
|---|---|---|
| `profile_evolve` | `profile_evolve.handle_profile_evolve` | Background LLM analysis of recent conversation → update user profile |
| `memory_dream` | `_handle_memory_dream` | Trigger memory dream optimization (merge duplicates + build links + decay) |
| `memory_distill` | `_handle_memory_distill` | Extract facts/preferences from conversation and save to memory |
| `agent_execute_slow_tool` | `_handle_slow_tool` | Execute slow tools (web search, file ops) asynchronously, feed back via SSE |

These are registered at module load time via `register_task_handler()` and consumed by the framework `task_worker.py`.

## Sub-agent Support

The module exposes `spawn_subagent` as a public action in manifest (`min_role: viewer`). Agent can spawn sub-agents to execute independent tasks in parallel, each with its own context, tool set, and conversation scope.

## Completed Capabilities

| Phase | Capability |
|---|---|
| **A Conversation trunk** | Session CRUD + SSE streaming conversation (real model, token-by-token) + message persistence (`agent_messages`) |
| **B Tools/Skills** | Progressive skill discovery (3 meta-tools); tool loop (non-stream decision + `recover_tool_calls` fallback + `call_capability` execution → result fed back → streaming final reply) |
| **C Intelligence** | Reference traceability (auto-extracted from `tool_events`); thinking display (stored in `agent_message_meta.thinking`, Text field, no overflow) |
| **D UX** | Complete frontend: conversation sidebar, message area, streaming bubbles, tool bubbles, thinking bubbles, references panel, model selector, long-context trimming (`MAX_CONTEXT_MESSAGES=24`) |
| **E Three-layer prompt system** | System prompt, enterprise prompt, and per-user auto-evolving profile; automatically merged into system message on each chat |
| **E2 Event sourcing** | Append-only event store (`agent_events`) recording every model interaction, projectable to messages |
| **E3 Engine orchestration** | Budget allocator, compressor, fallback chain, stuck detector, layered memory, experience memory |
| **E4 Background pool** | 4 registered task handlers: profile_evolve, memory_dream, memory_distill, agent_execute_slow_tool |
| **E5 Sub-agent** | Agent can spawn sub-agents for parallel independent task execution |
| **E6 Governance** | Per-agent config console, sensitive action approval workflow, admin overview/dashboard |

## Event Sourcing

Conversation history is dual-persisted:
- `agent_messages` / `agent_message_meta` — fast read for UI display
- `agent_events` — append-only event log for replay, analysis, and state reconstruction

The engine uses `event_store.py` for `record_event`, `read_events`, and `project_to_messages`.

## Governance

| Feature | Description |
|---|---|
| Per-agent config | Admin can configure model, budget, permissions per agent via management console |
| Sensitive action approval | Actions flagged as sensitive are held for admin approval before execution |
| Admin overview | Conversation replay, token usage, tool call history, cost dashboard |
| Admin endpoints | `/api/agent/admin/*` — overview stats, approval list, approve/reject, agent config CRUD |

## Three-Layer Prompt System

| Layer | Table | Content | Maintained By |
|---|---|---|---|
| System Prompt | `agent_system_prompt` | Agent execution boundary, personality, and rules | 1 global record, admin |
| Enterprise Prompt | `agent_enterprise_prompt` | Company knowledge, rules, and scripts | 1 global record, admin |
| User Profile | `agent_user_profile` | Per-user habits: tone, taboos, focus, habits | 1 per user, **auto-evolved** |

### Prompt Merge

On each chat, `build_context_messages(db, owner_id, history)` retrieves all three layers and merges them into a single system message:

```
<system prompt content>

---

<enterprise prompt content>

---

<user profile content>
```

### User Profile Auto-Evolution

1. After every N user messages (controlled by `EVOLVE_EVERY_N_MESSAGES = 3`), a background task (`task_type = "profile_evolve"`) is submitted to `framework_system_task_queues`.
2. The framework worker (`task_worker.py`) picks up the task and calls the `profile_evolve` handler.
3. The handler uses the LLM gateway (`deepseek-v4-flash`) to analyze recent conversation messages and extract structured profile data (tone, taboos, focus, habits).
4. The new profile is merged with the existing one and saved back to `agent_user_profile` with an incremented version and timestamp.
5. Throttling: evolution is skipped if the last evolution was less than 30 minutes ago.

### Admin Prompt Management

Admin users (`require_permission("admin")`) can update system and enterprise prompts via:

| Endpoint | Method | Purpose |
|---|---|---|
| `/api/agent/system-prompt` | GET | Get current system prompt |
| `/api/agent/system-prompt` | PUT | Update system prompt (admin) |
| `/api/agent/enterprise-prompt` | GET | Get current enterprise prompt |
| `/api/agent/enterprise-prompt` | PUT | Update enterprise prompt (admin) |
| `/api/agent/user-profile` | GET | Get current user's profile |

No prompt UI is shown in the frontend toolbar — all three layers are injected transparently.

## Backend API

All under `/api/agent` prefix.

| Endpoint | Method | Purpose |
|---|---|---|
| `/health` | GET | Module health check |
| `/profiles` | GET | List model profiles |
| `/tools` | GET | List discovered tools (skills → function calling definitions) |
| `/system-prompt` | GET/PUT | Get/update system prompt (PUT requires admin) |
| `/enterprise-prompt` | GET/PUT | Get/update enterprise prompt (PUT requires admin) |
| `/user-profile` | GET | Get current user's auto-evolved profile |
| `/conversations` | GET | List conversations |
| `/conversations` | POST | Create a conversation |
| `/conversations/{id}` | PATCH | Rename a conversation |
| `/conversations/{id}` | DELETE | Soft delete a conversation |
| `/conversations/{id}/messages` | GET | List messages with metadata (thinking, references, tool_events) |
| `/chat` | POST | Streaming chat via SSE: 3-layer prompt → tool_call → tool_result → thinking → token → [DONE] |
| `/admin/overview` | GET | Admin overview dashboard |
| `/admin/approvals` | GET | List pending sensitive action approvals |
| `/admin/approvals/{id}/approve` | POST | Approve a pending action (admin) |
| `/admin/approvals/{id}/reject` | POST | Reject a pending action (admin) |
| `/admin/agent-config` | GET/PUT | Get/update per-agent configuration (admin) |

## Chat Flow

```
User message → persist user message
  ├─ ensure_default_prompts() (on first chat)
  ├─ ensure_user_profile() (on first chat per user)
  ├─ build_tools(role) → 3 meta-tools (skill_list/skill_describe/skill_use)
  ├─ engine.装配上下文(db, conv_id, input, profile_key, owner_id)
  │     ├─ read events → project to messages
  │     ├─ budget_allocator → context assembly
  │     │     └─ if over budget → compressor (truncate from middle)
  │     ├─ layered_memory → inject relevant memories
  │     ├─ experience_memory → inject relevant success experiences
  │     └─ → combined message list
  ├─ fallback_chain.chat_with_fallback(messages, tools=...) → model decision
  │     ├─ try: primary model → fallback → cheap → echo
  │     ├─ stuck_detector check after each turn
  │     └─ tool_calls? YES → check_action_allowed → execute → feed result → loop
  │     └─ none → chat_stream_with_fallback → SSE token/thinking → [DONE]
  ├─ persist assistant message + meta + event
  └─ submit profile_evolve / memory_dream tasks (throttled)
```

## Tables (agent_ prefix, no foreign keys)

| Table | Purpose |
|---|---|
| `agent_conversations` | Conversation (owner_id, title, status) |
| `agent_messages` | Message (conversation_id, role, content) |
| `agent_message_meta` | Message metadata (thinking, references JSON, tool_events JSON) |
| `agent_system_prompt` | Global system prompt (admin-managed) |
| `agent_enterprise_prompt` | Global enterprise prompt (admin-managed) |
| `agent_user_profile` | Per-user auto-evolved profile (tone, taboos, focus, habits) |
| `agent_events` | Append-only event log (event_type, payload JSON, llm_response_id) |
| `agent_configs` | Per-agent configuration (model, budget, permissions) |
| `agent_pending_approvals` | Sensitive action approval queue |

## Background Task Handlers

Registered via `handlers/tasks.py` (4 handlers):

| Task type | Purpose | Throttle |
|---|---|---|
| `profile_evolve` | Analyze conversation → update user profile | 30 min cooldown |
| `memory_dream` | Trigger memory self-optimization | per user, interval-based |
| `memory_distill` | Extract facts/preferences from chat | per conversation |
| `agent_execute_slow_tool` | Execute expensive tool asynchronously | none |

## Real Model Verification

Using `deepseek-v4-flash` (framework gateway connected to OpenCode go subscription):

```
data: {"type": "tool_call", "name": "skill_use", "arguments": "{\"name\": \"_self__echo\"}"}
data: {"type": "tool_result", "name": "skill_use", "result": {...}}
data: {"type": "token", "content": "调用 echo 工具成功，它原样回显了参数"}
data: [DONE]
```

Message metadata preserved with `tool_events`, `references`, and `thinking` per assistant message.

## Framework Dependencies (import only, never modify)

- `app.gateway.router.gateway_router` — model gateway (chat, chat_stream, generate_image)
- `app.database` (`get_db`, `AsyncSessionLocal`) — database sessions
- `app.schemas.common.ApiResponse` — unified response
- `app.middleware.auth.require_permission` — auth dependency
- `app.services.module_registry` (`list_capabilities`, `call_capability`) — cross-module calls
- `app.services.task_worker` (`register_task_handler`) — background task registration
- `app.models.base.Base` — table base class
- `app.models.system.SystemTaskQueue` — task queue table
- `app.services.model_services` (`get_embedding`) — for memory operations
- `app.gateway.router.MODEL_PROFILES` — model context budget profiles

## Sandbox

```bash
cd modules/agent/sandbox && bash run.sh
# Backend: 127.0.0.1:38010, Frontend: 127.0.0.1:5180
# Uses production DB + real gateway + fixed dev user
```

Sandbox frontend port is fixed to **5180** (vite.config default + run.sh), deliberately avoiding the
main framework's 5173 so the two never fight over the port. The sandbox has its OWN login form
(`sandbox/src/App.vue`) because it has no framework login session — this shell does NOT run inside the
main framework. In the main framework the Agent loads `modules/agent/frontend/index.vue` and auth is
handled by the framework (runtime SDK `authHeaders()`), so `App.vue` is sandbox-only.

## Key Design Decisions

- **Progressive tool discovery**: 3 meta-tools (skill_list/skill_describe/skill_use) instead of flat capability list — constant token cost regardless of module count.
- **Engine orchestration**: `装配上下文()` in engine.py assembles all context layers; `fallback_chain` handles model degradation; `stuck_detector` prevents infinite loops.
- **Event sourcing**: Append-only event log enables conversation replay, analysis, and state reconstruction.
- **Tool decision uses non-stream** `gateway_router.chat` for reliable `tool_calls`.
- **Final reply uses** `gateway_router.chat_stream` (or `chat_stream_with_fallback`) for token-by-token UX.
- `_normalize_parameters()` converts framework capability params to valid JSON Schema.
- `recover_tool_calls()` in `model_client.py` falls back to raw provider response when adapter misses `tool_calls`.
- **Context compression**: `compressor.py` removes middle turns when token budget is exceeded, preserving system prompt and latest user input.
- **Fallback chain**: primary → backup → cheap → echo (last resort).
- **Three-layer prompt system**: system + enterprise + user profile merged into one system message at chat start.
- **Profile evolution**: background task with LLM analysis, throttled to avoid excessive model calls.
- **Experience memory**: Success path distillation stored as vector-indexed experiences, matched semantically on new input.
- **Sub-agent**: Agent can delegate tasks to sub-agents via `spawn_subagent` public action.
- No prompt UI in frontend: all three layers are invisible to end users.
- **Governance**: Per-agent config in DB, sensitive actions require approval, admin dashboard for oversight.
