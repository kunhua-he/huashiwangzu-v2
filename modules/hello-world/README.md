# Hello World Module

Sample module for scaffolding and integration testing.

## Capability

No HTTP API or capability registered. Used as a minimal verification target in framework tests.

## Verification

```bash
cd modules/hello-world/sandbox
npm install
npm run build

cd ../../../frontend
npm run build

cd ..
backend/.venv/bin/python dev_toolkit/module_sandbox_matrix.py --check
```

Expected result: `hello-world` passes through its sandbox frontend build and remains registered in the main frontend build. There is no `sandbox/test_module.py` because this sample has no backend router, samples, data tables, or cross-module capability.
