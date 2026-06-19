# DOCX Parser Module

Parse DOCX files into unified content blocks (paragraphs, tables, inline images).

## API

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/docx-parser/health` | GET | Module health check (public, no auth) |
| `/api/docx-parser/parse` | POST | Parse DOCX file by `file_id` |

## Capability

| Module | Action | Input | Output |
|--------|--------|-------|--------|
| `docx-parser` | `parse` | `{"file_id": int}` | Unified content block skeleton |

## Dependencies

- `python-docx` (in backend venv)

## Format Support

- `.docx` — Paragraphs, tables, inline images

## Verification

```bash
# Health check
curl http://127.0.0.1:33000/api/docx-parser/health

# Parse a file
curl -X POST http://127.0.0.1:33000/api/docx-parser/parse \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <token>" \
  -d '{"file_id": <id>}'
```

