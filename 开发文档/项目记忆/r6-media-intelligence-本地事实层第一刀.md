---
name: "R6 media-intelligence 本地事实层第一刀"
type: "task"
tags: [r6, media-intelligence, local-facts, ffprobe, pillow, degraded]
agent: "codex-r6-media-local-facts-c"
created: "2026-07-03T16:05:37.550274+00:00"
---

## 做了什么
- 将 media-intelligence 的 `local_algorithms.placeholder` 替换为 `local_algorithms.local_facts`。
- 图片事实层使用 Pillow 抽取 width/height/format/mode/frame_count/is_animated，并生成 `average_intensity_hash` 本地指纹向量。
- 视频事实层运行时检测 ffprobe，存在时解析 duration/width/height/frame_rate/codec/bit_rate/audio_stream_count，并基于 duration 生成 timeline keyframe markers；缺失或失败时返回结构化 `degraded`（含 code/dependency/message/install_command），不假装成功。
- pipeline 增加顶层 `degraded` 汇总；small_model/VLM 改为 rule-based/not_configured 的结构化 degraded，不再使用 placeholder provider/status。
- 更新 manifest/router/frontend/README 文案，避免对外能力元数据继续说 placeholder。
- 扩展 sandbox 测试：图片 happy path 真实 metadata、ffprobe missing degraded、happy path 输出不含 placeholder 字符串。

## 验证
- `mcp lint` 覆盖 media-intelligence backend providers/router/pipeline/base/registry 与 sandbox test：全部通过。
- `mcp run_test target=modules/media-intelligence/sandbox/test_module.py`：6 passed。
- 手动 `PYTHONPATH=backend:. backend/.venv/bin/python -m pytest modules/media-intelligence/sandbox/test_module.py -q`：6 passed。
- `/api/health` probe：200 ok。
- 临时 PNG 实际样例：provider=`local_algorithms.local_facts`，metadata 含 width=4 height=5 format=png mode=RGB，embedding algorithm=`average_intensity_hash`，`contains_placeholder=false`。
- ffprobe 缺失 monkeypatch 样例：status=`degraded`，degraded codes 含 `ffprobe_missing` 和安装建议 `brew install ffmpeg`。

## 边界说明
- 本任务修改文件均在 `modules/media-intelligence/`。
- 收工时全仓已出现并发外部 dirty：`dev_toolkit/`、`frontend/tests/`、`modules/knowledge/`、以及已有项目记忆文件；未修改、未回退这些外部变更。finish_task 因这些外部 dirty 显示边界失败。

## 残留风险
- OCR、object detector、small model、VLM 都仍是明确 degraded，不是 fake success；后续需要独立接真实引擎/模型。
- 当前 keyframes 是 ffprobe timeline markers，不落 thumbnail/frame artifact 文件。
