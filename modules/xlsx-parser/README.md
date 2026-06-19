# XLSX Parser Module

Parse XLSX and CSV files into unified content blocks.

## API

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/xlsx-parser/health` | GET | Module health check (public, no auth) |
| `/api/xlsx-parser/parse` | POST | Parse XLSX/CSV file by `file_id` |

## Capability

| Module | Action | Input | Output |
|--------|--------|-------|--------|
| `xlsx-parser` | `parse` | `{"file_id": int}` | Unified content block skeleton |

## Dependencies

- `openpyxl` (in backend venv)
- Standard library `csv` for CSV parsing

## Format Support

- `.xlsx`, `.xls` — Sheet-wise table blocks
- `.csv` — CSV content as table blocks

## Verification

```bash
# Health check
curl http://127.0.0.1:33000/api/xlsx-parser/health

# Parse a file
curl -X POST http://127.0.0.1:33000/api/xlsx-parser/parse \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <token>" \
  -d '{"file_id": <id>}'
```

