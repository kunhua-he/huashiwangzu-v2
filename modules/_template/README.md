# Module Template

Copy this directory to create a new module.

## Quick Start

```bash
# 1. Copy the template
cp -r modules/_template modules/YOUR_MODULE_KEY

# 2. Replace placeholders (case-sensitive):
#    MODULE_KEY          → your-module-key
#    MODULE_DISPLAY_NAME → Your Module Display Name
#    SANDBOX_PORT        → unique port number (check existing sandboxes)
#
#    Files to update:
#      manifest.json
#      sandbox/package.json
#      sandbox/index.html
#      sandbox/vite.config.ts
#      sandbox/src/App.vue

# 3. Install and run
cd modules/YOUR_MODULE_KEY/sandbox
npm install
npm run dev
```

## Directory Structure

```
modules/{module_key}/
  manifest.json          ← Module identity (name, icon, permissions, window spec, backend router)
  frontend/              ← Your Vue components and business logic
    index.vue            ← Entry component (referenced by manifest.component_key)
  backend/               ← (Optional) Python FastAPI router
    router.py            ← Export `router = APIRouter(prefix="/api/xxx")`
  runtime/               ← Runtime middle layer (copied from _template)
    index.ts             ← getApiUrl(), getModuleConfig(), hasPermission()
  sandbox/               ← Independent dev environment
    package.json         ← npm dependencies
    vite.config.ts       ← Vite config with proxy to backend
    runtime.config.json  ← Sandbox settings (API URL, permissions, module prefs)
    index.html           ← Entry HTML
    src/main.ts          ← Vue app bootstrap
    src/App.vue          ← Sandbox shell wrapping your module entry
```

## Sandbox Development

- `npm run dev` starts the sandbox at a unique port
- API calls to `/api/*` are proxied to the main backend
- The sandbox imports your module entry via `@modules/MODULE_KEY/frontend/index.vue`
- When development is complete, run `cd frontend && npm run build` to verify integration

## If the Sandbox Template Isn't Enough

The sandbox is a minimal shell. If your module needs framework features that aren't available:

1. Copy the relevant framework code from `frontend/src/` into your sandbox
2. Common files to copy: shared composables, API helpers, UI components, auth mock
3. Add any extra dependencies to `sandbox/package.json`

The goal is that your module frontend code (`modules/{name}/frontend/`) never imports from
`@/` (framework) — it only imports from `../runtime` and `@modules/...` (other modules).
