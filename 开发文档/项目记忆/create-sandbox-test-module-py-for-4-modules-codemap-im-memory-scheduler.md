---
name: "Create sandbox test_module.py for 4 modules (codemap, im, memory, scheduler)"
type: task
tags: ["sandbox", "test_module", "codemap", "im", "memory", "scheduler", "contract-validation"]
created: 2026-07-02
agent: opencode
---

## 改了什么

Created sandbox contract validation tests for 4 modules that previously had empty sandbox/ directories:

1. **modules/codemap/sandbox/test_module.py** — 18 tests covering all 13 public_actions (get_file, impact, check_boundary, module_map, search, stats, rebuild, acquire_lock, check_lock, release_lock, list_locks, report_inaccuracy, list_feedback) plus output shape validation for file info, impact, boundary check, lock, and unified response.

2. **modules/im/sandbox/test_module.py** — 8 tests covering notify and send actions, including empty content rejection, missing required field detection, and output shape validation.

3. **modules/memory/sandbox/test_module.py** — 20 tests covering all 16 public_actions (save, recall, list, delete, fuse, rethink, replace, insert, dream, save_experience, match_experience, experience_feedback, overview_stats, recall_stable_rules, recall_chunk, save_stable_rule) plus output shapes for memory, experience, and stable rule objects.

4. **modules/scheduler/sandbox/test_module.py** — 12 tests covering create, list, cancel actions, including invalid datetime rejection, empty action detection, zero task_id detection, and output shape validation for task objects with/without recurrence.

## 验证了什么

All 4 test files run successfully with:
```
PYTHONPATH=backend backend/.venv/bin/python modules/<key>/sandbox/test_module.py
```

Each validates:
- Required parameter presence
- Parameter types (int, str, list, bool)
- Value ranges (positive ints, non-empty strings, enum values)
- Output object shapes with required fields
- Unified response shape {success, data, error}

No real external calls, no DB writes, no temp files.
