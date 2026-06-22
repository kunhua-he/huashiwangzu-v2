# pdf-viewer — PDF file viewer

## Responsibility
Opens and renders PDF files in the desktop shell using PDF.js. Pure frontend viewer — no backend, no cross-module capabilities.

## Public capabilities
None. Passive file viewer only.

## HTTP endpoints
None. No `route_prefix` and no backend router.

## Data tables
None.

## How to query/use
The desktop shell opens this viewer automatically when a user double-clicks a `.pdf` file (matching `supported_formats`). Uses `sort_order: 30` for file-open scheduling.

## Boundaries/notes
- Frontend-only module; no backend or runtime.
- Relies on the framework's file preview API for fetching PDF content.
- Window default size 950×700, supports multiple instances.
