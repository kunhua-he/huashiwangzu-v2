# Current Contracts

## Unified API Envelope

```json
{ "success": true, "data": {}, "error": null }
```

Business errors must raise framework exceptions or return a unified failure envelope. Legacy `code != 0`, `success=false`, or `error` payloads must not be wrapped as outer success.

Semantic failure has one authority:

- Backend code uses `backend/app/services/semantic_failure.py`.
- Toolkit/release code uses `dev_toolkit/semantic_failure.py`.
- A payload is failed when any level contains `success:false`, a non-empty `error`, `status:"failed"` / `status:"error"`, or legacy `code != 0`.
- `success:true` with nested `error` is a failure. Do not treat HTTP 200, command exit completion, or an outer success envelope as business success.

## Cross-Module Calls

Backend request body:

```json
{
  "target_module": "knowledge",
  "action": "search",
  "parameters": { "query": "..." }
}
```

- Backend path: `/api/modules/call`.
- Frontend path: `platform.modules.call(targetModule, action, parameters)`.
- Runtime `register_capability` is authoritative.
- Manifest `public_actions` is discovery metadata and must match runtime registration.

Authorization has two separate identities:

| Field | Meaning | Source |
|---|---|---|
| `caller` | Business subject and data owner, usually `user:{id}` | Authenticated user or `on_behalf_of_user_id` |
| `actor` / `system:*` principal | Executing service that is allowed to perform framework background work | `module_registry` whitelist |

Rules:

- Module code must not self-report privilege by passing `caller_role="admin"` or `caller_role="editor"` with a `user:*` caller.
- HTTP/user entrypoints call `call_capability_for_user(...)`; role comes from login/auth dependency.
- Background framework work calls `call_capability_as_system(..., principal="system:*", on_behalf_of_user_id=...)`.
- Unknown `system:*` principals are denied. Add a principal only when it is a framework-level service, not for a module convenience path.

## Data Ownership

| Owner | Prefix |
|---|---|
| Framework | `framework_*` |
| Agent | `agent_*` |
| Knowledge | `kb_*` |
| Memory | `memory_*` |
| Excel engine | `excel_*` |
| Image generation | `imagegen_*` |
| IM | `im_*` |
| Docs open | `docs_*` |
| Douyin delivery | `douyin_*` |
| WeChat writer | `wechat_*` |
| Codemap | `codemap_*` |

Modules use logical IDs for cross-owner references. They must not add database foreign keys to framework or other module tables.

## File Access

Any endpoint or capability that reads file content by `file_id` must validate owner/share access through framework file access checks before reading disk.

## Content IR

Canonical flow:

```text
Agent / Parser -> Content IR -> validate_ir -> normalize_ir -> write_ir -> DB canonical source -> compile/publish
```

- DB is the canonical source for structured content.
- LLM output is not trusted; validators are the authority.
- Agent cannot directly create or replace framework physical files. It writes structure first and explicitly publishes artifacts/files when requested.

## Frontend Runtime

Modules use runtime/platform APIs for auth, files, office, gateway, tasks, notifications, logs, settings, and module calls. Module frontend code must not import desktop shell internals.

The shell injects `window.platform`:

- `platform.api.request/get/post` uses the shared Axios client, token injection, envelope handling, and 401/403 handling.
- `platform.modules.call/capabilities` is the frontend capability path.
- `platform.modules.openApp(appKey, params)` is the only normal way for modules to open apps.

`openApp` must route through the desktop app handle so app disabled state and user role checks run before the window manager opens anything. `__HSWZ_WINDOW_MANAGER__` is legacy fallback only; new module code must not call it directly.

## Validation Jobs

Tool jobs expose command state and business cleanliness separately:

| Field | Meaning |
|---|---|
| `command_completed` | The process produced a parseable terminal result, even if the result contains failures |
| `command_success` | Process exit code was zero |
| `passed` | The checked domain had no blocker failures |
| `clean_success` / `success` | Fully clean result: no blockers and no tracked debt |
| `has_debt` | Skips, warnings, or known non-blocking debt remain |

Release and sandbox tooling must never mark `success:true` only because a command finished. `PASS_WITH_DEBT`, sandbox skips, failed matrix entries, and semantic-failure task results must stay machine-visible.

## Terminal Tools Boundary

Terminal execution is local but locked to `data/workspaces/{user_id}/`. Host desktop/files are not exposed. Drafts become desktop files only through explicit publish/import capabilities.
