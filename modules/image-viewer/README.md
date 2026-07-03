# image-viewer — Image viewer for common image formats

## Responsibility
Opens and renders image files (png, jpg, jpeg, gif, bmp, webp, svg, ico) in the desktop shell. Pure frontend viewer — no backend, no cross-module capabilities.

## Public capabilities
None. Passive file viewer only.

## HTTP endpoints
None. No `route_prefix` and no backend router.

## Data tables
None.

## How to query/use
The desktop shell opens this viewer automatically when a user double-clicks a matching image file (highest `sort_order: 10` among file-viewers). Other modules cannot invoke it.

## Boundaries/notes
- Frontend-only module; no backend or runtime.
- Default window 900×650, supports multiple instances.
- SVG is supported for viewing (not editing).

## Sandbox verification

```bash
cd modules/image-viewer/sandbox
npm install
npm run build

cd ../../../frontend
npm run build

cd ..
backend/.venv/bin/python dev_toolkit/module_sandbox_matrix.py --check
```

Expected result: `image-viewer` passes through its sandbox frontend build. There is no `sandbox/test_module.py` because this module has no backend router, no samples, and no cross-module capability.
