# web-tools — Web search and page fetching (no API key)

## Responsibility
Provides web search (DuckDuckGo HTML search) and web page content fetching for agents. No API key required — uses `ddgs` for search and `httpx + lxml` for page extraction. SSRF protection blocks internal network addresses.

## Public capabilities

| Capability | Parameters | Returns | min_role |
|---|---|---|---|
| `web-tools:search` | `query` (str), `top_k` (int, default 8, max 20) | `{results: [{title, url, snippet}], error}` | viewer |
| `web-tools:fetch` | `url` (str), `max_chars` (int, default 8000) | `{url, title, text, truncated, error}` | viewer |

## HTTP endpoints

All under `/api/web-tools`:

| Method | Path | Purpose |
|---|---|---|
| GET | `/health` | Module health check |
| POST | `/search` | DuckDuckGo web search |
| POST | `/fetch` | Fetch and extract web page text content |

## Data tables
None. Stateless module.

## How to query/use
Agent discovers `web-tools__search` and `web-tools__fetch` as function tools. Call via `call_capability("web-tools", "search", {...})` or `call_capability("web-tools", "fetch", {...})`.

## Boundaries/notes
- **Search**: Uses DuckDuckGo HTML endpoint via `ddgs` library, region `cn-zh`, safesearch moderate. Tries proxy (`WEB_TOOLS_PROXY` env or `http://127.0.0.1:4780`) first, falls back to direct.
- **Fetch**: SSRF-protected via `app.core.url_safety.validate_safe_url` — blocks internal/private IP ranges (localhost, 10.x, 172.16-31.x, 192.168.x, etc.), cloud metadata endpoints (169.254.169.254), non-http(s) schemes, embedded credentials, and DNS lookups to private addresses (fail-closed on DNS failure). Rejects binary content types early. Strips script/style/nav/footer before extracting text.
- **Proxy**: Default proxy is `http://127.0.0.1:4780` (ClashX common port); customizable via `WEB_TOOLS_PROXY` env var.
- Background-service window type, not shown in launcher.
- Timeouts: search 10s, fetch 15s, max content 5MB.
