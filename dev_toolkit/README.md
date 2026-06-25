# 项目工具台 MCP Server

开工先连我。`python3.14 dev_toolkit/server.py` (stdio), 注册在 `.mcp.json`。

通过 MCP 协议暴露 15 个开发加速工具, 供 AI agent 直接调用。

## 工具清单

### 全景感知
| 工具 | 说明 |
|------|------|
| `brief()` | 项目全景: README + 最近变更 + 投递箱待处理 + 最近 Git 提交 + 最近项目记忆(带 agent)。返回末尾含默认工作流建议。 |
| `maturity(area)` | 成熟度评分卡: 按 coverage/quality/completeness 打分 8 个维度。无参数返回全景排序。 |

### 代码探索与修改验证
| 工具 | 说明 |
|------|------|
| `code_explore(query)` | codegraph 探索: 查符号/调用链/影响面 |
| `code_node(symbol)` | codegraph 查符号或文件定义 |
| `code_impact(path)` | codegraph 查文件改动的影响面 |
| `lint(path)` | ruff 静态检查 Python 文件 |

### 接口与能力查询
| 工具 | 说明 |
|------|------|
| `routes(filter)` | 从 openapi.json 查端点(方法/路径/参数) |
| `capabilities(module)` | 扫描模块 manifest.json 查准能力+参数 |
| `db_schema(table)` | 查数据库表结构(列名/类型/nullable) |

### 系统探测
| 工具 | 说明 |
|------|------|
| `probe(method, path, body)` | 自动登录后打后端任意 HTTP 接口。返回含 `_evidence_assessment` 证据判定(PASS/FAIL + 建议)。 |
| `call_capability(module, action, params)` | 调模块能力(跨模块)。返回含 `_evidence_assessment` 证据判定。 |
| `tail_log(module, lines)` | 查看模块日志尾部 |
| `log_errors(module, lines)` | ★扫日志里被try/except吞掉的异常(Traceback/Exception/violation/错参). **后台/异步功能做完后必调**:有命中=没跑通别报通过 |
| `sql(query)` | 只读 SQL 查询(SELECT/WITH/EXPLAIN) |
| `web_read(url)` | 读网页返回 markdown 正文 |

### 记忆与归因
| 工具 | 说明 |
|------|------|
| `memory_search(query, k)` | 语义+关键词搜索项目记忆 |
| `memory_write(type, title, body, tags, agent)` | 写入项目记忆, agent 字段用于归因 |
| `memory_recent(n)` | 最近 N 条记忆 |

### 测试 / 回归
| 工具 | 说明 |
|------|------|
| `run_test(target)` | 跑单个测试(文件/用例)不跑全局 |
| `smoke_all()` | 一键全模块回归红绿矩阵(也可 `python3.14 dev_toolkit/smoke.py`)。**注:当前断言偏浅有假绿/假红,待"修smoke可信度"批修准** |

## 默认工作流（每个开发 agent 必遵）

```
brief → codegraph → probe/call_capability → memory_write → (codegraph不准时) report_inaccuracy
```

1. **开工 → `brief()`** 看全貌 + 投递箱待处理。
2. **查代码 → `code_explore`/`code_node`/`code_impact`** (codegraph 首选 → codemap 次选 → 实读兜底)。
3. **查准端点/能力/表 → `routes`/`capabilities`/`db_schema`**。
4. **改完静态查错 → `lint`** (ruff)。
5. **验证 → `probe`/`call_capability`** 打活系统（不打日志，先黑箱）。结果含 `_evidence_assessment` 证据判定。
6. **单测 → `run_test`**，不跑全局。
7. **收工 → `memory_write(agent="<自己>")`** 落条归因。
8. **不准 → `codemap report_inaccuracy`** 反馈偏差。

## 成熟度

- `maturity()` — 评分卡，8 维度按 coverage/quality/completeness 打分排序。
- 用于规划升级优先级：总分最低的维度优先投入。
