# office-gen — Office document generator

## Responsibility
Generates and converts office documents (docx, xlsx, pptx, pdf) from structured JSON data. Uses python-docx, openpyxl, python-pptx, and fpdf2 for generation, and LibreOffice headless for format conversion. All output files are saved to the framework file system (content-addressed).

## Public capabilities

5 capabilities registered:

| Capability | Parameters | Returns | min_role |
|---|---|---|---|
| `office-gen:docx` | `filename` (str), `content` ([block]), `folder_id` (int?) | `{file_id, name, size, ...}` | editor |
| `office-gen:xlsx` | `filename` (str), `sheets` ([{name, columns, rows}]), `folder_id` (int?) | `{file_id, name, size, ...}` | editor |
| `office-gen:pptx` | `filename` (str), `slides` ([{title, bullets, notes}]), `folder_id` (int?) | `{file_id, name, size, ...}` | editor |
| `office-gen:pdf` | `filename` (str), `content` ([block]), `folder_id` (int?) | `{file_id, name, size, ...}` | editor |
| `office-gen:convert` | `file_id` (int), `target_format` (str, default "pdf") | `{file_id, name, size, ...}` | editor |

Content blocks for docx/pdf: `{type: 标题\|段落\|表格\|图片, text, level, bold, align, header?, rows?}`.
Sheets for xlsx: `{name, columns: [str], rows: [[any]]}`.
Slides for pptx: `{title, bullets: [str\|{text, level}], notes?}`.

## HTTP endpoints

All under `/api/office-gen`:

| Method | Path | Purpose |
|---|---|---|
| GET | `/health` | Health check (+ LibreOffice availability) |
| POST | `/docx` | Generate Word document |
| POST | `/xlsx` | Generate Excel spreadsheet |
| POST | `/pptx` | Generate PowerPoint presentation |
| POST | `/pdf` | Generate PDF document |
| POST | `/convert` | Convert between office formats |

## Data tables
None. Output files are stored as framework files (`framework_file_items`).

## How to query/use
Agent discovers `office-gen__docx` / `office-gen__xlsx` / etc. as function tools. Call via `call_capability("office-gen", "docx", {...})`. Also accessible via HTTP POST endpoints for direct testing.

## Boundaries/notes
- File generation uses `generator.py` (python-docx, openpyxl, python-pptx, fpdf2).
- Format conversion uses `converter.py` (LibreOffice headless) — requires `libreoffice` on PATH.
- All generated files are persisted via framework `file_upload_service` (content-addressed dedup).
- Validation: `filename` and content blocks/sheets/slides required; `converter.convert_by_file_id` is async.
- The `/convert` endpoint validates file access via `check_file_access` before reading from disk.
