---
name: "修复 im:send capability 会话成员权限校验"
type: "task"
tags: [im, capability, permission]
agent: "W7"
created: "2026-07-02T11:41:53.810766+00:00"
---

改了什么：modules/im/backend/router.py 新增 _send_text_message_to_conversation，共用 HTTP /api/im/messages 与 im:send capability 的会话存在、membership 校验、写消息和摘要更新逻辑；im:send 不再接受非 user caller/sender_id 回退，system 通知继续走 im:notify。

验证了什么：ruff check ../modules/im/backend/router.py tests/test_im_capability_permissions.py 通过；pytest tests/test_im_capability_permissions.py -q 1 passed；backend/.venv/bin/python modules/im/sandbox/test_module.py PASS。

是否还有残留风险：工作区有大量既有未提交改动，未触碰/未还原；未重启常驻后端做 live probe，ASGI 回归测试已覆盖真实 app/DB。

关联 commit：未提交。
