---
name: "media-asr 模块新增 — 视频提取音频与音频转写"
type: task
tags: ["media-asr", "asr", "whisper", "ffmpeg", "audio-extraction", "module", "模块新增"]
created: 2026-06-30
agent: opencode
---

## 新增模块

创建了 `modules/media-asr/` 模块，包含 3 个 capability：

### 文件

```
modules/media-asr/
  manifest.json           — 模块声明：media-asr key, editor 角色, 视频/音频格式
  README.md               — 模块文档
  backend/router.py       — FastAPI router: health + 3个端点 + capability 注册
  backend/services/audio_service.py  — ffmpeg 提取音频 + mlx_whisper 转写
  frontend/index.vue      — 最小前端组件
```

### 三个 capability

| 能力 | 参数 | 说明 |
|------|------|------|
| `media-asr:extract_audio` | file_id, sample_rate, audio_format, save_file, folder_id | 视频→音频，ffmpeg 参数列表调用 |
| `media-asr:transcribe_audio` | file_id, model, language, save_text, folder_id | 音频→文字，mlx_whisper |
| `media-asr:transcribe_video` | file_id, model, sample_rate, language, save_audio, save_text, folder_id | 视频→提取→转写，一步完成 |

### 设计要点

- 文件读取使用 `run_uploaded_file_capability` + `check_file_access`
- 保存文件使用 `upload_file_from_path`，同名冲突自动加时间戳重试
- ffmpeg 子进程使用参数列表（禁止 shell=True）
- mlx_whisper import 在函数内，缺依赖时返回明确错误
- 临时文件用 `tempfile.TemporaryDirectory()` 自动清理
- 模型名映射：large-v3 → mlx-community/whisper-large-v3-mlx（HuggingFace repo）
- no_proxy 环境变量含 `::1` 会破坏 httpx/HF 连接，代码中临时清理

### 依赖状态

- `mlx_whisper 0.4.3` — 需安装到 `backend/.venv/`（`pip install mlx-whisper`），含 torch 2.12.1 + mlx 0.31.2
- `ffmpeg 8.1` — 系统可用
- 首次运行 mlx_whisper 会自动从 HuggingFace 下载模型（~3GB）

### 验证结果

| 测试 | 结果 |
|------|------|
| health GET | ✅ 200 OK |
| capabilities 注册 | ✅ 3个能力全部注册 |
| transcribe_audio (silent.wav) | ✅ 返回 text/segments/blocks |
| extract_audio (silent.mp4) | ✅ 返回 audio_file_id |
| transcribe_video (no save) | ✅ text + segments |
| transcribe_video (save both) | ✅ audio_file_id + text_file_id |
| 测试文件清理 | ✅ 5个文件已删除, 临时文件已清理 |
| git diff --name-only | ✅ 零输出（全是新文件，未改现有代码） |

### 未做

- 抖音链接下载/扫码登录/Cookie/账号态（已确认不在此轮范围）
- 长视频耗时警告、模型首次加载状态提示（后续迭代可加）

