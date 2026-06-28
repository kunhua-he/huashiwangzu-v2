---
name: "Workflow recipe 匹配器升级"
type: task
tags: ["agent", "workflow-recipe", "matching", "recall", "tests"]
created: 2026-06-28
agent: zcode
---

优化 workflow recipe 匹配器：从简单空格 token overlap 升级为混合召回，包括中文归一化、字符 bigram Jaccard、领域意图别名、工具名提示和 confidence 混排。覆盖场景包括“我桌面有什么文件”“帮我打开桌面的文件”“看一下桌面里的 xlsx”“输出成 excel”“覆盖旧表格”等。新增 test_workflow_recipe.py，验证相关 paraphrase 能召回、无关查询低分。
