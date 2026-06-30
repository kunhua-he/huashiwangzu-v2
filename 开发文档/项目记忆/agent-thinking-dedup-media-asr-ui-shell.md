---
name: "Agent thinking dedup + media-asr UI shell"
type: task
tags: ["agent", "thinking", "dedup", "media-asr", "ui", "commit-15756fc7"]
created: 2026-06-30
agent: opencode
---

## Changed files

- `modules/agent/backend/runtime/tool_loop_runtime.py` — Agent thinking dedup fix
- `modules/media-asr/runtime/index.ts` — new file, framework SDK copy
- `modules/media-asr/frontend/index.vue` — full UI workspace rewrite
- `modules/media-asr/manifest.json` — show_in_launcher: true
- `modules/media-asr/README.md` — updated with UI usage

## Thinking duplication root cause

When `enable_single_pass_streaming_tools` is True:
1. `_stream_until_tool_or_done()` streams thinking tokens one-by-one → appends each chunk to `thinking_parts` (line 1036) + yields each as SSE (line 1038)
2. Lines 289-297 then reprocess `result.get("thinking")` → re-appends full aggregated text to `thinking_parts` + re-emits in 10-char chunks

Fix: Guard thinking re-emission with `if not self.policy.enable_single_pass_streaming_tools`. Non-streaming path unchanged.

## media-asr UI

Uses `platform.modules.call('media-asr', action, params)` for capability invocation and `platform.files` for file upload. Three modes (video→text, extract audio, audio→text) with configurable parameters. Result shows full transcript + timestamped segment table + saved file IDs.

## Tests

- 127 agent tests passed (4 suites)
- ruff lint clean
- npm run build passed

## Not verified

- Real transcription not run (requires ffmpeg + mlx_whisper + a media sample)
- The fix was applied at the Agent runtime layer; no provider adapter changes
