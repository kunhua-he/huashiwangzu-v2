---
name: "修smoke_all可信度 · 杀假绿/假红"
type: task
tags: ["smoke", "testing", "false-green", "false-red", "regression"]
created: 2026-06-23
agent: opencode
---

opencode 执行投递箱"修smoke可信度"任务。

改动: dev_toolkit/smoke.py

修法:
1. 断言改判内层 success(_cap_ok 函数), 删除 or status==200 兜底
2. im send: 先建/查会话获 conversation_id 再发
3. office-gen: 参数名 filename(非 file_name)+block content
4. image-vision: upload png→file_id→describe
5. excel-engine: openpyxl 造真 xlsx→upload→parse
6. docs-open: 改 POST + call capability
7. A5 recycle: 修响应解析(列表非 items 包装)+origin_id匹配
8. 加环境健康检查(bge-m3)

验收: 26场景全绿; 假绿证实测旧判GREEN新判RED;

git diff --name-only: dev_toolkit/smoke.py
