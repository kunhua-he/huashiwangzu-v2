# im — Internal messaging (IM) module

## Responsibility
Provides user-to-user and system-to-user messaging within the desktop shell: conversation management, message sending/reading, unread counts, and user listing. Supports both HTTP API and cross-module capability invocation.

## Public capabilities

| Capability | Parameters | Returns | min_role |
|---|---|---|---|
| `im:notify` | `user_id` (int), `content` (str), `title` (str?) | `{success, message_id}` | editor |
| `im:send` | `conversation_id` (int), `content` (str) | `{success, message_id}` | viewer |

`notify` pushes a system notification to a user's IM (creates or reuses a conversation with system user `id=0`). `send` sends a message to an existing conversation on behalf of the caller.

## HTTP endpoints

All under `/api/im`:

| Method | Path | Purpose |
|---|---|---|
| GET | `/conversations` | List current user's conversations with unread counts |
| GET | `/conversations/{id}/messages` | List messages in a conversation (paginated) |
| POST | `/messages` | Send a message (to existing conv or auto-create with target_user_id) |
| POST | `/conversations/{id}/read` | Mark messages as read up to a given message_id |
| GET | `/unread-count` | Total unread count across all conversations |
| GET | `/users` | List system users available for chat (excludes self) |

## Data tables

All `im_*` prefix:

| Table | Purpose |
|---|---|
| `im_conversations` | Conversation (type, members, last_message_summary) |
| `im_messages` | Messages (conversation, sender, content, type) |
| `im_read_states` | Per-user per-conversation last_read_message_id |

## How to query/use
Agent and other modules push notifications via framework `call_capability("im", "notify", {...})`. Scheduler module uses `im:notify` to deliver scheduled task results.

## Boundaries/notes
- Conversation members stored as JSON array in `member_ids` column (no join table).
- System user `id=0` is a virtual identity for system notifications.
- `notify` capability requires `editor` role; `send` requires `viewer`.
- Database tables are auto-created on first use via `run_init()`.
