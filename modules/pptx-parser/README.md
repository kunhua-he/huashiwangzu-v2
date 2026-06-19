# PPTX Parser Module

Parse PPTX files into unified content blocks (slide text, picture detection).

## API

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/pptx-parser/health` | GET | Module health check (public, no auth) |
| `/api/pptx-parser/parse` | POST | Parse PPTX file by `file_id` |

## Capability

| Module | Action | Input | Output |
|--------|--------|-------|--------|
| `pptx-parser` | `parse` | `{"file_id": int}` | Unified content block skeleton |

## Dependencies

- `python-pptx` (in backend venv)

## Format Support

- `.pptx` — Slide text, picture detection

## Verification

```bash
# Health check
curl http://127.0.0.1:33000/api/pptx-parser/health

# Parse a file
curl -X POST http://127.0.0.1:33000/api/pptx-parser/parse \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <token>" \
  -d '{"file_id": <id>}'
```

