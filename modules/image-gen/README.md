# image-gen — Image generation via framework gateway

## Responsibility
Generates images from text prompts using the framework's centralized model gateway (GPTStore gpt-5.5 for real generation). Falls back to PIL placeholder images when the gateway's image generation provider is not configured.

## Public capabilities

| Capability | Parameters | Returns | min_role |
|---|---|---|---|
| `image-gen:generate` | `prompt` (str), `size` (str, default "1024x1024"), `style` (str?), `count` (int, default 1) | `{images: [{file_id, name, size, placeholder}]}` | editor |

Generated images are saved to the framework file system via `file_upload_service` (content-addressed).

## HTTP endpoints

All under `/api/image-gen`:

| Method | Path | Purpose |
|---|---|---|
| GET | `/health` | Module health check |
| POST | `/generate` | Generate image(s) from prompt |

## Data tables
None. Generated images are saved as framework files (`framework_file_items`), not in module-specific tables.

## How to query/use
Agent discovers `image-gen__generate` as a function tool and calls it via `call_capability("image-gen", "generate", {...})`.

## Boundaries/notes
- Image generation goes through the framework gateway router (`gateway_router.generate_image`), not direct HTTP calls.
- When `GPTSTORE_API_KEY` is not configured, falls back to PIL placeholder with a "developing" watermark.
- Validation: `prompt` must be non-empty; `size` must match `WxH` pattern (e.g. `1024x1024`).
- Generated images are uploaded to the caller's file space with filename `image-gen_{timestamp}_{n}.png`.
