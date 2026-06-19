# Agent Module — AI Assistant

## Goal

Production-grade AI assistant for the V2 desktop shell. Multi-session, streaming, tool-discovery, three-layer prompt system, traceable citations, and auto-evolving user profiles. All business code and tables inside `modules/agent/`.

## Completed Capabilities

| Phase | Capability |
|---|---|
| **A Conversation trunk** | Session CRUD + SSE streaming conversation (real model, token-by-token) + message persistence (`agent_messages`) |
| **B Tools/Skills** | Skill discoverer (`build_tools` from `list_capabilities`); tool loop (non-stream decision + `recover_tool_calls` fallback + `call_capability` execution → result fed back → streaming final reply) |
| **C Intelligence** | Reference traceability (auto-extracted from `tool_events`); thinking display (stored in `agent_message_meta.thinking`, Text field, no overflow) |
| **D UX** | Complete frontend: conversation sidebar, message area, streaming bubbles, tool bubbles, thinking bubbles, references panel, model selector, long-context trimming (`MAX_CONTEXT_MESSAGES=24`) |
| **E Three-layer prompt system** | System prompt, enterprise prompt, and per-user auto-evolving profile; automatically merged into system message on each chat |

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

## Chat Flow

```
User message → persist user message
  ├─ ensure_default_prompts() (on first chat)
  ├─ ensure_user_profile() (on first chat per user)
  ├─ build_tools(role) → tool definitions from framework capability registry
  ├─ build_context_messages(db, owner_id, history)
  │     ├─ get_system_prompt()       ← agent_system_prompt (admin-managed)
  │     ├─ get_enterprise_prompt()   ← agent_enterprise_prompt (admin-managed)
  │     └─ get_active_user_profile() ← agent_user_profile (auto-evolved)
  │     → merged system message
  ├─ gateway_router.chat(non-stream, tools=...) → model decision
  │     ├─ tool_calls? YES → call_capability → feed result → loop (≤5 rounds)
  │     │                      └─ recover_tool_calls() fallback when adapter misses extraction
  │     └─ none → gateway_router.chat_stream(stream) → SSE token/thinking → [DONE]
  ├─ persist assistant message + meta (thinking, references, tool_events)
  └─ submit profile_evolve task (throttled) → background LLM analysis → update agent_user_profile
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

## Background Task Handler

The module registers a `profile_evolve` task handler via `register_task_handler()`:

- **Task type**: `profile_evolve`
- **Parameters**: `{ "conversation_id": int, "owner_id": int }`
- **Handler**: `profile_evolve.handle_profile_evolve()` — uses LLM gateway to analyze recent conversation and update profile
- **Throttle**: Skips if last evolution < 30 minutes ago; triggered every 3 user messages

## Real Model Verification

Using `deepseek-v4-flash` (framework gateway connected to OpenCode go subscription):

```
data: {"type": "tool_call", "name": "_self__echo"}
data: {"type": "tool_result", "name": "_self__echo", "result": {...}}
data: {"type": "token", "content": "调用 echo 工具成功，它原样回显了参数"}
data: [DONE]
```

Message metadata preserved with `tool_events`, `references`, and `thinking` per assistant message.

## Framework Dependencies (import only, never modify)

- `app.gateway.router.gateway_router` — model gateway
- `app.database` (`get_db`, `AsyncSessionLocal`) — database sessions
- `app.schemas.common.ApiResponse` — unified response
- `app.middleware.auth.require_permission` — auth dependency
- `app.services.module_registry` (`list_capabilities`, `call_capability`) — cross-module calls
- `app.services.task_worker` (`register_task_handler`) — background task registration
- `app.models.base.Base` — table base class
- `app.models.system.SystemTaskQueue` — task queue table (for submitting profile_evolve tasks)

## Sandbox

```bash
cd modules/agent/sandbox && bash run.sh
# Backend: 127.0.0.1:38010, Frontend: 127.0.0.1:5180
# Uses production DB + real gateway + fixed dev user
```

## Key Design Decisions

- Tool discovery is dynamic: reads `list_capabilities(role)` → no hardcoded tools.
- Tool decision uses non-stream `gateway_router.chat` for reliable `tool_calls`.
- Final reply uses `gateway_router.chat_stream` for token-by-token UX.
- `_normalize_parameters()` converts framework capability params to valid JSON Schema.
- `_tool_calls_for_history()` normalizes `arguments` to JSON string for OpenAI-compatible format.
- `recover_tool_calls()` in `model_client.py` falls back to raw provider response when adapter misses `tool_calls`.
- Long context: `MAX_CONTEXT_MESSAGES=24`, older messages collapsed into system summary hint.
- Three-layer prompt system: system + enterprise + user profile merged into one system message at chat start.
- Profile evolution: background task with LLM analysis, throttled to avoid excessive model calls.
- No prompt UI in frontend: all three layers are invisible to end users.
