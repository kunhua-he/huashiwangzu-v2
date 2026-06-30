---
name: "media-asr模块验收审查与小修"
type: task
tags: ["media-asr", "review", "repair", "ffmpeg", "mlx-whisper", "capability"]
created: 2026-06-30
agent: codex
---

审查并小修 opencode 新增的 media-asr 模块。确认模块边界在 modules/media-asr/ 内，能力注册与 health 可用，ffmpeg/mlx_whisper 环境可用。发现并修复两个小问题：transcribe_video(save_audio=true) 使用 upload_file_from_path 会 rename 临时音频导致后续转写读不到文件，改为上传副本；LLM 工具参数字符串化时 save_* 和 folder_id 解析不稳，新增布尔/可选整数解析。补充 audio_format/sample_rate 白名单校验。验证：ruff lint router/audio_service 通过，python3.14 py_compile 通过，GET /api/media-asr/health 200，capabilities 可见三个 media-asr 能力。
