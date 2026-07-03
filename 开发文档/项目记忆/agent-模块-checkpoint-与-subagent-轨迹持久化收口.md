---
name: "Agent 模块 checkpoint 与 subagent 轨迹持久化收口"
type: "task"
tags: [agent, checkpoint, trajectory, subagent, module-boundary, quality]
agent: "codex-agent-module-worker-20260703-r1"
created: "2026-07-03T06:09:12.587769+00:00"
---

# 做了什么
- 仅修改 `modules/agent/**`：清理 `models.py` 中 `AgentUsageDaily` 重复 `__table_args__`。
- 将 `AgentCheckpoint` ORM 和 `init_db.ensure_checkpoint_table` 对齐到运行时真实 checkpoint schema：`checkpoint_id`、`parent_checkpoint_id`、`step`、`channel_values`、`extra_meta`，并为旧表补列/释放旧 `checkpoint_type NOT NULL`/补唯一约束。
- `subagent_runner` 现在返回实际 `tool_calls` / `tool_results`。
- `agent:spawn_subagent(track_trajectory=True)` 现在会把每个子任务的工具调用、工具结果、结论持久化到 `agent_trajectory_records`；未传 `conversation_id` 时使用临时负数编号，未传 `turn_index_offset` 时追加到该 conversation 当前最大 turn 后，避免覆盖旧轨迹。
- 同步 `manifest.json`、`bootstrap.py` 和 `README.md` 的公开参数与行为说明。

# 验证结果
- `ruff check`：`modules/agent/backend/models.py`、`init_db.py`、`handlers/tool.py`、`services/subagent_runner.py`、`bootstrap.py`、`test_subagent_runner.py` 全通过。
- `pytest modules/agent/backend/test_subagent_runner.py`：2 passed。
- `pytest backend/tests/test_checkpointer.py`（通过 run_test 单跑，cwd=backend）：12 passed。
- `pytest modules/agent/backend/test_repair09.py::{test_record_turn_typed_jsonb_upsert,test_two_turns_two_trajectories,test_trajectory_unique_index_exists}`：3 passed。
- `pytest modules/agent/sandbox/test_module.py`：6 passed。
- 活系统探针：`GET /api/agent/health`、`GET /api/agent/admin/overview` 均 200 success。

# 边界/风险
- 开工时 `worktree_guard(module_key='agent')` 干净；收工时全局工作区出现大量 `backend/`、`dev_toolkit/`、其他模块和项目记忆改动，疑似并行 agent 写入。未 revert。我的触碰文件通过 `git diff -- modules/agent` 确认为 8 个，均在 `modules/agent/**`。
- `finish_task` 已调用但因为全局并行 dirty 导致边界失败；它的组合 test_targets 还触发了 run_test 工作目录归一化问题，单跑同一测试是通过的。
- 未真实调用 `spawn_subagent` 以避免生产库留下长期测试轨迹；持久化路径用 mock 单测 + trajectory/checkpointer DB 集成测试覆盖。

# 关联 commit
- 尚未提交。
