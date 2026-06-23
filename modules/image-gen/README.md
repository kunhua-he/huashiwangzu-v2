# image-gen — Multi-provider template adapter architecture

## Responsibility
Generates images from text prompts using a pluggable multi-provider adapter architecture. Supports multiple image service providers (LiblibAI Star-3, GPTStore gpt-5.5, PIL placeholder fallback) via template configuration.

## Architecture

```
modules/image-gen/backend/
├── router.py                 # Thin dispatch layer
├── providers/
│   ├── __init__.py           # Adapter registry + credential check
│   ├── base.py               # ImageProvider ABC + GenSpec/GenResult
│   ├── liblib.py             # LiblibAI (HMAC-SHA1 + async poll)
│   ├── gptstore.py           # Wraps existing gateway.generate_image
│   └── placeholder.py        # PIL placeholder (credential-less fallback)
└── image_templates.json      # Provider + template config (models.json pattern)
```

## Public capabilities

| Capability | Parameters | Returns | min_role |
|---|---|---|---|
| `image-gen:generate` | `prompt` (str), `size` (str, default "1024x1024"), `aspect_ratio` (str?), `count` (int, default 1), `steps` (int, default 30), `template` (str, default from config) | `{images: [{file_id, name, size, placeholder}], template, points_cost, balance}` | editor |
| `image-gen:list_templates` | — | `{templates: [{key, label, provider, available}]}` | viewer |
| `image-gen:usage_history` | `limit` (int, default 20) | `{records: [...]}` | editor |

Generated images are saved to the framework file system via `file_upload_service`. Costs are tracked in `imagegen_records`.

## HTTP endpoints

All under `/api/image-gen`:

| Method | Path | Purpose |
|---|---|---|
| GET | `/health` | Module health check |
| POST | `/generate` | Generate image(s) from prompt |
| GET | `/templates` | List available templates |
| GET | `/history` | Query personal generation history |

## Data tables
- `imagegen_records` — Generation history with points cost tracking. Created automatically at module load time.

## How to add a service provider template

Three steps:

1. **Write an adapter** in `providers/` — subclass `ImageProvider`, implement `async def generate(self, spec: GenSpec) -> list[GenResult]`. Handle signing, request, polling, parsing yourself. Do NOT handle URL download / DB persistence.
2. **Add a template entry** in `image_templates.json` — under `templates`, add a key with `provider` (matching your adapter's `provider_key`), API paths, env var names for credentials, and any provider-specific config.
3. **Add credentials** to `backend/.env` — use the env var names declared in the template config. Never hardcode keys in JSON or Python.

Providers are registered in `providers/__init__.py:_PROVIDERS` and auto-discovered at runtime.

## Chinese prompt support
When a template has `prompt_language: "en"` and the input prompt contains Chinese characters, it is automatically translated to English via the framework gateway before submission.

## Boundaries/notes
- Adapters handle auth/signing/request/polling/parsing. They do NOT download URLs or persist to DB.
- When a template's required credentials are missing, the system auto-downgrades to placeholder (no hard error).
- Validation: `prompt` must be non-empty; either `size` (WxH) or `aspect_ratio` must be provided.
