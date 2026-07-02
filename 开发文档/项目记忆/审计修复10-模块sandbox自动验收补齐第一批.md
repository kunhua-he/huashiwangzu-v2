---
name: "审计修复10-模块Sandbox自动验收补齐第一批"
type: task
tags: ["sandbox", "test", "module-matrix"]
created: 2026-07-02
agent: opencode
---

为9个已有sandbox目录但缺test_module.py的模块补齐自动验收测试：csv-parser、markdown-parser、structured-parser、email-parser（inline parser合约）、terminal-tools（安全合约）、douyin-delivery、wechat-writer、agent、knowledge（schema contract test）。矩阵从8 pass/0 fail/26 skip提升至17 pass/0 fail/17 skip。ruff通过，release gate中sandbox PASS（BLOCKER为队列历史债）。新增9个test_module.py文件，均在modules/<key>/sandbox/范围内。
