# Image Vision Module

Describe image content via the framework gateway vision model.

## API

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/image-vision/health` | GET | Module health check (public, no auth) |
| `/api/image-vision/describe` | POST | Describe image file by `file_id` |

## Capability

| Module | Action | Input | Output |
|--------|--------|-------|--------|
| `image-vision` | `describe` | `{"file_id": int}` | Image description text |

## Dependencies

- `Pillow` / `PIL` (in backend venv)
- Framework gateway (`app.gateway.router.gateway_router`) for vision inference

## Format Support

- `.jpg`, `.jpeg`, `.png`, `.gif`, `.webp`, `.bmp`, `.ico`

## Behaviour

1. Tries the gateway vision model with a multi-modal chat prompt
2. Falls back to basic image metadata (dimensions, mode, file name) if vision model unavailable

## Verification

```bash
# Health check
curl http://127.0.0.1:33000/api/image-vision/health

# Describe
curl -X POST http://127.0.0.1:33000/api/image-vision/describe \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <token>" \
  -d '{"file_id": <id>}'
```

