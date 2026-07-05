---
name: "Parser/Media Content IR 二期标准化与真实样本矩阵"
type: "task"
tags: [content-ir, parser, media, csv-parser, xlsx-parser, media-asr, media-intelligence, matrix]
agent: "codex"
created: "2026-07-05T07:58:22.991565+00:00"
---

关联代码提交：859b9b12 feat: standardize parser media content ir。

做了什么：CSV/XLSX 原生输出 spreadsheet IR（top-level sheet，table.data.headers/rows/start_cell/range/source_ref）；media-asr transcript blocks 增加 source_ref.time_start/time_end/timecode 并输出 content-ir/v1 text IR；media-intelligence/image-vision 新输出 schema_version 收口到 content-ir/v1，media-intelligence metadata 增加 adapters 分层状态，degraded/not_configured 不伪装为真实语义成功；normalizer 明确把历史 1.0 迁移为 content-ir/v1。

真实样本矩阵（parse -> normalize -> validate -> write）：

| module | sample | capability | raw output | normalized IR | validate | write | debt |
|---|---|---|---|---|---|---|---|
| text-parser | sandbox/samples/sample.txt | parse | text | content-ir/v1 text | pass | content_package | none |
| markdown-parser | sandbox/samples/sample.md | parse | mixed | content-ir/v1 mixed | pass | content_package | none |
| csv-parser | sandbox/samples/sample.csv | parse | spreadsheet | content-ir/v1 spreadsheet, top sheet | pass | excel_engine | none |
| xlsx-parser | sandbox/samples/sample.xlsx | parse | spreadsheet | content-ir/v1 spreadsheet, 2 sheets | pass | excel_engine | none |
| docx-parser | sandbox/samples/sample.docx | parse | document | content-ir/v1 document | pass | content_package | none |
| pdf-parser | sandbox/samples/sample.pdf | parse | document | content-ir/v1 document | pass | content_package | none |
| pptx-parser | sandbox/samples/sample.pptx | parse | presentation | content-ir/v1 presentation | pass | content_package | none |
| email-parser | sandbox/samples/sample.eml | parse | mixed | content-ir/v1 mixed | pass | content_package | none |
| structured-parser | sandbox/samples/sample.json | parse | text | content-ir/v1 text | pass | content_package | none |
| image-vision | sandbox/samples/sample.png | describe | image | content-ir/v1 image | pass | resource | none |
| media-intelligence | generated-invalid-video.mp4 | extract_keyframes | mixed degraded | content-ir/v1 mixed | pass | content_package | OCR/object/VLM/small-model may remain degraded/not_configured until adapters are configured |
| media-asr | stubbed-sample.wav | transcribe_audio | text | content-ir/v1 text with segment timecode | pass | content_package | ASR model boundary stubbed in test; router/capability contract and timestamp IR are real |

验收：ruff targeted command passed；test_content_ir_architecture.py 63 passed；test_content_ir_parser_media_matrix.py 1 passed；csv/xlsx/media-intelligence sandbox combo 15 passed with PYTHONPATH/import-mode adjustment；media-asr sandbox + matrix 6 passed；/api/health ok。
