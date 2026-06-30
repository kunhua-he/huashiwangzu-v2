---
name: "新增 macOS/Windows 一键部署脚本"
type: task
tags: ["deploy", "scripts", "postgres", "proxy", "bootstrap"]
created: 2026-06-30
agent: codex
---

# 改了什么
新增仓库级一键部署能力：`scripts/deploy_common.py`、`scripts/deploy_mac.sh`、`scripts/deploy_windows.ps1`。macOS 脚本通过 Homebrew 自动安装缺失依赖，Windows 脚本通过 winget/Chocolatey 自动安装缺失依赖；两者都提示代理配置，代理默认只作用于当前进程，写入全局 git/npm 配置前会二次确认。

`deploy_common.py` 负责补齐 `backend/.env`、生成 `JWT_SECRET`、创建 PostgreSQL 数据库、安装 `vector`/`pg_trgm` 扩展、调用框架 `init_db`/`seed`/manifest sync，并发现模块 `init_db.py` 中的 `run_init`、`_run_startup_init` 或 `ensure_*tables` 幂等初始化入口。

同步修正 `scripts/start_dev.sh` 端口提示 30004 -> 33000，并在 `开发文档/README.md` 增加一键部署说明。

# 验证了什么
通过 `bash -n scripts/deploy_mac.sh scripts/start_dev.sh`、`python3 -m py_compile scripts/deploy_common.py`、`python3 scripts/deploy_common.py --help`、工具台 `lint(path="scripts/deploy_common.py")`。工具台 `probe /api/health` 返回 status ok。

# 是否还有残留风险
没有实际执行一键部署，避免在当前机器安装/重启系统依赖或改动数据库。Windows PowerShell 语法解析检查因本机没有 `pwsh` 未运行。工作区有大量既有脏改，本任务只新增/修改部署相关文件。

# 关联 commit
未提交。
