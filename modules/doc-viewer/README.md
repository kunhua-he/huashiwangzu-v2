# doc-viewer — Document viewer for docx/doc files

## Responsibility
Opens and renders `.docx` / `.doc` files in the desktop shell. Pure frontend viewer — no backend, no parse capability. Delegates file access to the framework's file service and preview endpoint.

## Public capabilities
None. This is a passive file viewer — it does not expose any cross-module capability.

## HTTP endpoints
None. No `route_prefix` and no backend router.

## Data tables
None. No `doc_viewer_*` tables.

## How to query/use
The desktop shell automatically opens this viewer when a user double-clicks a `.docx` or `.doc` file (matching `supported_formats`). Other modules cannot invoke it via capability calls.

## Boundaries/notes
- Frontend-only module; no backend router.
- Relies on the framework's file preview endpoint to fetch document content.
- Uses `sort_order: 40` for file-open scheduling (priority between pdf-viewer 30 and ppt-viewer 50).

## Sandbox verification

```bash
cd modules/doc-viewer/sandbox
npm install
npm run build

cd ../../../frontend
npm run build

cd ..
backend/.venv/bin/python dev_toolkit/module_sandbox_matrix.py --check
```

Expected result: `doc-viewer` passes through its sandbox frontend build. There is no `sandbox/test_module.py` because this module has no backend router, no samples, and no cross-module capability.
