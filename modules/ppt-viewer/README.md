# ppt-viewer — PowerPoint file viewer

## Responsibility
Opens and renders `.pptx` / `.ppt` presentation files in the desktop shell. Pure frontend viewer — no backend, no cross-module capabilities.

## Public capabilities
None. Passive file viewer only.

## HTTP endpoints
None. No `route_prefix` and no backend router.

## Data tables
None.

## How to query/use
The desktop shell opens this viewer when a user double-clicks a `.pptx` or `.ppt` file. Uses `sort_order: 50` for file-open scheduling (lowest priority among file-viewers).

## Boundaries/notes
- Frontend-only module; no backend or runtime.
- Default window 1000×700, supports multiple instances.
- Relies on framework file service to fetch presentation content.

## Sandbox verification

```bash
cd modules/ppt-viewer/sandbox
npm install
npm run build

cd ../../../frontend
npm run build

cd ..
backend/.venv/bin/python dev_toolkit/module_sandbox_matrix.py --check
```

Expected result: `ppt-viewer` passes through its sandbox frontend build. There is no `sandbox/test_module.py` because this module has no backend router, no samples, and no cross-module capability.
