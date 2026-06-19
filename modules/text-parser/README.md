# Text/Markdown Parser Module

Parse TXT and Markdown files into unified content blocks.

## API

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/text-parser/health` | GET | Module health check (public, no auth) |
| `/api/text-parser/parse` | POST | Parse text/markdown file by `file_id` |

## Capability

| Module | Action | Input | Output |
|--------|--------|-------|--------|
| `text-parser` | `parse` | `{"file_id": int}` | Unified content block skeleton |

## Dependencies

- No third-party libraries. Pure standard library.

## Format Support

- `.txt`, `.text`, `.log` — Paragraph-grouped plain text
- `.md`, `.markdown` — Heading-aware, code block-aware, paragraph grouping

## Verification

```bash
# Health check
curl http://127.0.0.1:33000/api/text-parser/health

# Parse a file
curl -X POST http://127.0.0.1:33000/api/text-parser/parse \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <token>" \
  -d '{"file_id": <id>}'
```

