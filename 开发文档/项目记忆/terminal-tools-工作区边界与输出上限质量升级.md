---
name: "terminal-tools 工作区边界与输出上限质量升级"
type: "task"
tags: [terminal-tools, module-boundary, safety, workspace, output-cap, cleanup]
agent: "codex-terminal-tools-worker-20260703-r1"
created: "2026-07-03T06:23:04.457779+00:00"
---

## 做了什么
- 收口 terminal-tools 子进程输出：exec/run_python 改为 stdout/stderr 先写工作区临时文件，再按 1MB 上限读取，避免无限输出先进内存。
- 文件能力加固：write/import 不再返回 absolute_path；read_file 最多返回 1MB 并带 truncated；list_workspace 最多返回 1000 项并带 truncated；路径越界 ValueError 统一消毒为 `Path escapes workspace boundary`。
- run_python 加固：input_files 经 check_file_access 后使用安全文件名复制到本次 `.da_{run_id}` 临时目录，finally 清理；TMPDIR/HOME/WORKSPACE 均指向工作区。
- chart 防假成功：run_python 成功但未上传图表时改为 success:false。
- README 与 sandbox/test_module.py 更新验收矩阵和安全契约。

## 验证
- ruff 通过：modules/terminal-tools/backend/router.py、handlers/*.py、sandbox/test_module.py。
- py_compile 通过：router.py、handlers/*.py、sandbox/test_module.py。
- `python3.14 modules/terminal-tools/sandbox/test_module.py` 通过。
- 直接模块回归通过：write/read/list/path escape/dangerous exec/output cap/run_python no-code/chart invalid；测试工作区 `data/workspaces/909901` 已清理。

## 限制与风险
- 活系统 probe/call_capability 未执行成功：127.0.0.1:33000 无监听，工具台返回 All connection attempts failed。
- 全仓存在大量其他 worker 的 dirty 文件，worktree_guard(module_key=terminal-tools) 因外部 dirty 返回 false；本次实际产品 diff 仅 `modules/terminal-tools/` 6 个文件。
- 底层 backend workspace_security logger 仍可能在服务日志记录绝对路径；terminal-tools 返回给调用方的错误已消毒。

## 关联 commit
- 未提交。
