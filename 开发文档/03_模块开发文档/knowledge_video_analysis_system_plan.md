# 知识库视频分析体系参考源码调研与落地方案

更新时间：2026-07-03  
参考源码目录：`/Users/hekunhua/Documents/Agent/reference_sources`  
目标模块：`modules/knowledge/`

## 1. 本次完成事项

### 1.1 reference_sources 目录排序与重构

当前顶层目录已整理为稳定编号结构：

| 目录 | 用途 |
|---|---|
| `00_catalog/` | 参考源清单、调研索引、目录规则。 |
| `10_agent_platform_reference/` | Agent 平台、工作流、上下文工程参考。 |
| `20_document_ir_reference/` | 文档解析、Document IR、结构化内容参考。 |
| `30_media_analysis_reference/` | 视频/音频/图像分析参考，供知识库多媒体链路使用。 |
| `90_archive/` | 重复下载、历史快照、暂不活跃参考源。 |

已将重复的 `2026_06_25_extra_duplicate_core_frameworks` 移入：

```text
/Users/hekunhua/Documents/Agent/reference_sources/90_archive/2026_06_25_extra_duplicate_core_frameworks
```

已生成参考源清单：

```text
/Users/hekunhua/Documents/Agent/reference_sources/00_catalog/video_analysis_reference_catalog.md
```

### 1.2 通过 4780 代理新增下载的参考项目

新增下载到 `30_media_analysis_reference/` 的项目：

| 类别 | 项目 | 远程仓库 | 作用 |
|---|---|---|---|
| 视频解码/抽帧 | `decord` | `https://github.com/dmlc/decord.git` | 高吞吐随机访问、批量抽帧。 |
| 视频解码/抽帧 | `PyAV` | `https://github.com/PyAV-Org/PyAV.git` | FFmpeg 级容器、流、时间戳、硬件解码控制。 |
| 音频/ASR | `whisperX` | `https://github.com/m-bain/whisperX.git` | Whisper + VAD + 强制对齐 + 说话人分离。 |
| 嵌入/检索 | `FlagEmbedding` | `https://github.com/FlagOpen/FlagEmbedding.git` | BGE-M3、Visualized-BGE、多路召回/重排参考。 |
| 图谱 RAG | `microsoft-graphrag` | `https://github.com/microsoft/graphrag.git` | GraphRAG 索引、实体关系、community report。 |
| 多模态模型 | `LLaVA-NeXT` | `https://github.com/LLaVA-VL/LLaVA-NeXT.git` | LLaVA-Video 视频理解基线。 |
| 多模态模型 | `Qwen2.5-VL` | `https://github.com/QwenLM/Qwen2.5-VL.git` | 中文企业视频/图像理解主参考。 |
| 多模态模型 | `MiniCPM-V` | `https://github.com/OpenBMB/MiniCPM-V.git` | 低成本/端侧/本地 fallback VLM。 |
| 向量存储 | `lancedb` | `https://github.com/lancedb/lancedb.git` | 向量 + FTS + metadata filter + hybrid search 模式参考。 |

当前媒体分析目录：

```text
30_media_analysis_reference/
  00_pipeline_orchestration/        # 预留：生产 pipeline 编排参考
  05_video_decode_sampling/         # decord, PyAV
  10_scene_segmentation/            # PySceneDetect, TransNetV2
  20_vision_ocr_detection/          # PaddleOCR, sam2, ultralytics
  30_audio_asr/                     # FunASR, faster-whisper, whisperX
  40_embedding_retrieval/           # FlagEmbedding, fiftyone, open_clip
  50_dataset_annotation_quality/    # cvat
  60_video_rag_research/            # HKUDS-VideoRAG, starsuzi-VideoRAG, microsoft-graphrag
  70_multimodal_models/             # Qwen2.5-VL, MiniCPM-V, LLaVA-NeXT
  80_storage_vector_index/          # lancedb
```

## 2. 我们项目现状与约束

### 2.1 当前知识库链路

当前 knowledge 模块已经具备五层主链路：

1. 文档登记：`kb_documents`
2. Parser 统一解析：parser 模块输出 DocumentIr
3. 分块与向量化：`kb_chunks.embedding vector(1024)`，当前与 BGE-M3 维度匹配
4. 原始采集与页级融合：`kb_raw_data`、`kb_page_fusions`
5. 图谱与治理：`kb_entity_dictionary`、`kb_graph_nodes`、`kb_graph_edges`、治理候选等

当前公开能力包括：

- `knowledge:search`
- `knowledge:get_block`
- `knowledge:get_page_fusion`
- `knowledge:get_entity_dictionary`
- `knowledge:get_graph_context`
- `knowledge:get_pending_count`
- `knowledge:classify_pipeline_debt`
- `knowledge:get_evidence_detail`
- `knowledge:get_ocr_words`
- `knowledge:ingest`
- `knowledge:get_ingest_status`
- `knowledge:export`

### 2.2 必须遵守的架构边界

视频分析体系应当作为 knowledge 模块的能力演进，但要继续遵守现有架构规则：

1. **模块代码落在 `modules/knowledge/` 内**。  
   如果需要新增通用框架能力，例如新的模型网关端点，应作为独立框架任务提出。

2. **文件访问必须经过框架授权**。  
   按 `file_id` 获取视频文件时，不能裸读 `framework_file_items` 或直接拼路径。必须经框架公开文件访问能力或 `check_file_access` 等价链路。

3. **跨模块调用必须走统一通路**。  
   knowledge 调 parser、image-vision、未来 video-parser、model gateway，都应通过 `/api/modules/call`、capability registry 或框架公开服务入口，禁止 import 其他模块代码。

4. **多 worker 状态必须持久化**。  
   视频处理是长任务，阶段状态、锁、断点、进度、失败原因必须落库或文件原子写，不能依赖单进程内存。

5. **不要把 GraphRAG 或 VLM 做成第一版前置依赖**。  
   第一版要先让“视频可入库、可搜索、可跳转引用”稳定，再叠加视觉检索和图谱。

## 3. 参考项目结论：逐层取舍

## 3.1 解码与抽帧层

### decord

适合：

- 快速随机访问视频帧。
- 按 scene/segment 批量抽取代表帧。
- `VideoReader.get_batch(indices)` 一次取多个帧。
- `get_frame_timestamp(indices)` 映射帧到时间。

建议用法：

- 作为默认批量抽帧引擎。
- 用于每个 segment 的 first/middle/last 帧、均匀采样帧、OCR 候选帧。
- 注意将帧索引与时间戳持久化，避免后续引用失真。

风险：

- PyPI 通常 CPU-only；GPU/NVDEC 需要源构建。
- FFmpeg 报告的总帧数可能不准。
- 对可变帧率视频要优先相信 timestamp，而不是简单 `frame_index / fps`。

### PyAV

适合：

- 容器/流/codec/packet 级控制。
- 探测 metadata、音轨、视频流、时间基、keyframe。
- 特殊视频、损坏视频、硬件加速场景的 fallback。

建议用法：

- 作为 metadata probe 和 fallback decoder。
- 用于抽取音轨、检查视频是否可解码、确定 duration/fps/codec。
- 第一版不要做复杂 remux，只做读和抽取。

## 3.2 场景/镜头切分层

### PySceneDetect

适合：

- 可解释的阈值型 scene detection。
- `ContentDetector`、`AdaptiveDetector` 可快速落地。
- StatsManager 可输出 per-frame 指标，适合调阈值和做质量面板。

建议用法：

- 第一版默认使用时间窗口分段，例如 30 秒；同时可选 PySceneDetect 做 scene 辅助边界。
- 屏幕录制、PPT 讲解、培训视频容易出现低动态长镜头，不能只依赖 scene cut。
- 对企业会议类视频，scene cut 价值低于 ASR 时间段和话题段落。

### TransNetV2

适合：

- 学习型镜头边界检测。
- 比阈值检测更稳，但部署较麻烦。

建议用法：

- 第二阶段作为可选高质量 shot boundary 检测器。
- 不建议第一版依赖，因为 TensorFlow 旧版本/权重/转换成本较高。

## 3.3 OCR、目标检测、区域分割层

### PaddleOCR

适合：

- 中文/英文/多语言视频帧文字识别。
- PPT、屏幕录制、产品演示、培训材料、截图型视频。
- 识别结果可带文本框、置信度、行/词级坐标。

建议用法：

- 第一版必须纳入，作为视频入库的核心信息来源之一。
- 对每个 segment 的代表帧运行 OCR。
- 对相邻帧 OCR 结果做去重：相同字幕/同页 PPT 不要重复入库。
- OCR 结果进入 `visible_text` 和 `ocr_text`，同时保留 box 坐标，供未来播放器高亮。

### ultralytics YOLO

适合：

- 目标检测、跟踪、区域类元数据。
- 人、车辆、商品、设备、UI 元素等对象识别。

建议：

- 第一版可不引入，除非明确需要对象检索。
- 若引入，应只用 core predict/track 结果，避免使用会写文件/开窗口的 solution helper。
- 注意许可证：Ultralytics 源码 AGPL-3.0，企业产品要谨慎，必要时换 permissive 许可模型或购买商业授权。

### SAM2

适合：

- 用 YOLO/OCR box 作为 prompt，得到精细 mask。
- 对视频中的特定对象/区域做传播。

建议：

- 暂不作为第一版能力。
- 第二/三阶段用于“选中视频画面区域提问”“跨帧跟踪某个区域”等高级功能。

## 3.4 音频与 ASR 层

### 推荐主线：FunASR

FunASR 最适合我们这个中文企业知识库场景。

推荐第一版默认：

```python
AutoModel(
    model="paraformer-zh",
    vad_model="fsmn-vad",
    punc_model="ct-punc",
    spk_model="cam++",
    device="cuda",
)
```

如果没有 GPU 或只做本地 smoke：

```python
AutoModel(
    model="iic/SenseVoiceSmall",
    vad_model="fsmn-vad",
    spk_model="cam++",
    device="cpu",
)
```

优势：

- 中文识别能力强。
- 有 VAD、标点、时间戳、热词、说话人聚类。
- `sentence_info` 可作为视频 transcript chunk 的天然基础。
- 对中文企业术语、产品名、人名可以用 hotword 辅助。

注意：

- diarization 给的是匿名 speaker cluster，不是身份识别。
- `timestamp` / `timestamps` 字段在不同模型路径可能不一致，需要统一 normalization。
- vLLM 路径适合高吞吐实验，但不是第一版默认。

### faster-whisper

适合：

- Whisper 兼容、多语言 fallback。
- GPU/CPU 量化部署。
- 简单可靠，工程成熟。

建议：

- 作为 fallback，不作为中文主链路。
- 无内置说话人分离，speaker 需要额外模型。

### WhisperX

适合：

- 需要更准确 word-level subtitle timing。
- ASR + forced alignment + pyannote diarization。

建议：

- 作为“字幕级精修/对齐”可选能力。
- 不作为第一版默认，因为 HF/pyannote gated model、alignment model、依赖复杂度较高。

## 3.5 多模态/VLM 层

### 推荐主线：Qwen2.5-VL / Qwen-VL

Qwen 系列最适合中文企业视频理解主链路。

能力：

- 图像/视频输入。
- 本地路径、URL、frame list。
- `fps`、`nframes`、`min_frames`、`max_frames`、pixel budget 控制。
- 中文 OCR、中文指令、结构化抽取表现预期最好。

建议用途：

- segment 级视频描述。
- 关键帧理解。
- 视觉证据 + OCR + ASR 的初步融合。
- 生成结构化 JSON：时间线、事件、实体、屏幕文字、证据帧、置信度。

推荐提示词原则：

- 必须给 segment 时间范围。
- 必须给抽样帧时间戳。
- 明确只根据可见内容回答，不能猜。
- 只输出合法 JSON。
- 模型输出必须 JSON parse 校验，不合法则走 repair/retry。

### MiniCPM-V

适合：

- 低成本、本地、端侧、快速粗分析。
- 1.3B 级模型，部署成本远低于大 Qwen。

建议：

- 作为 fallback/triage：先低成本生成粗 caption，低置信度或高价值片段再升级到 Qwen。
- 适合本地离线、安全敏感、GPU 资源不足场景。

### LLaVA-NeXT / LLaVA-Video

适合：

- 研究基线。
- 对比 32/64 帧视频理解效果。
- 借鉴 frame timestamp prompt。

建议：

- 不作为生产默认。部署复杂、中文企业场景和 JSON 稳定性不如 Qwen。

## 3.6 嵌入、检索、GraphRAG 与向量存储层

### BGE-M3 / FlagEmbedding

我们项目当前 BGE-M3 与 `kb_chunks.embedding vector(1024)` 已高度匹配。

BGE-M3 可借鉴三路检索：

1. dense embedding：当前已具备。
2. sparse lexical：可先用 PostgreSQL FTS 替代。
3. ColBERT late interaction：后续高质量 rerank 再考虑。

建议：

- 视频第一版沿用 BGE-M3 text dense embedding。
- 对 segment 的 `content_text = transcript + OCR + VLM caption` 做 embedding。
- 未来增加 Visualized-BGE-M3 做图文统一检索。

### OpenCLIP / Visualized-BGE

建议：

- 第一版不必须做 visual embedding。
- 第二阶段引入：
  - OpenCLIP：轻量、通用 frame embedding。
  - Visualized-BGE-M3：更适合中文多模态统一空间。

### HKUDS-VideoRAG

最值得借鉴的结构：

- video_path
- video_segments
- text_chunks
- entities
- chunks
- video_segment_feature
- chunk_entity_relation

建议：

- 不照搬它的本地 JSON/HNSW 存储。
- 将逻辑 namespace 映射为 PostgreSQL 表。
- segment 是视频知识库的核心检索单元。

### Microsoft GraphRAG

值得借鉴：

- Document / TextUnit / Entity / Relationship / Claim / Community / Community Report。
- Local Search、Global Search、DRIFT Search。

建议：

- 第一版只做 segment text RAG。
- 第二阶段做实体/关系。
- 第三阶段做 community report，用于跨视频库全局问题。

### LanceDB

值得借鉴：

- vector + FTS + metadata filter + hybrid rerank。
- RRF 融合 dense/lexical 结果。

建议：

- 继续用 PostgreSQL + pgvector，不新增 LanceDB 服务。
- 用 PostgreSQL 复刻 LanceDB 模式：pgvector HNSW + tsvector GIN + metadata JSONB + RRF + reranker。

## 4. 推荐总体架构

## 4.1 核心心智模型

视频不要当成“一个大文档”处理，而要拆成：

```text
Video Asset
  └── Segment 1 [start_ms, end_ms]
        ├── ASR transcript sentences
        ├── OCR visible text
        ├── VLM scene caption
        ├── keyframes / frame timestamps
        ├── entities / events
        └── embeddings
  └── Segment 2 ...
```

也就是说：

- `kb_documents` 仍然代表用户上传的文件登记。
- 新增 `kb_media_assets` 表代表媒体资产 metadata。
- 新增 `kb_video_segments` 表代表可引用、可检索、可播放跳转的核心单元。
- `kb_chunks` 可以继续承载最终可检索文本块，但 segment 元数据需要独立表。

## 4.2 第一版 Pipeline

第一版目标：**视频上传后，可以入库、生成可搜索文本、搜索结果能跳到视频时间点，有阶段进度和失败可诊断。**

### Stage 0：文件登记与权限

输入：framework `file_id`。

处理：

1. 调框架文件访问校验。
2. 检查扩展名/mime：`mp4`、`mov`、`mkv`、`webm`、`avi`、`mp3`、`wav`、`m4a`。
3. 在 `kb_documents` 登记 document。
4. 建立 `kb_media_assets`。

输出：

- `document_id`
- `asset_id`

### Stage 1：媒体探测

用 PyAV/ffprobe 等价能力获取：

- duration_ms
- video_stream_count
- audio_stream_count
- width/height
- fps
- frame_count（可为空/不可信）
- codec
- bitrate
- rotation
- has_audio
- has_video

落库：`kb_media_assets.metadata_json`。

失败处理：

- 无视频但有音频：走 audio-only pipeline。
- 无音频但有视频：走 visual-only pipeline。
- 坏文件：stage failed，记录错误，不假绿。

### Stage 2：分段

第一版策略：

- 默认固定 30 秒分段。
- 如果视频短于 30 秒，则一个 segment。
- 如果启用 scene detection，可用 PySceneDetect 修正边界，但不要让过短 segment 泛滥。

建议参数：

```text
default_segment_seconds = 30
min_segment_seconds = 8
max_segment_seconds = 90
scene_detector = disabled | pyscenedetect_adaptive
```

落库：`kb_video_segments`。

每个 segment：

- segment_index
- start_ms
- end_ms
- duration_ms
- boundary_source: `fixed_time` / `scene_detected` / `audio_sentence` / `manual`
- status

### Stage 3：音频抽取与 ASR

处理：

1. 从视频抽取音频到临时工作目录。
2. 统一为 16kHz mono WAV/PCM。
3. 调 FunASR。
4. 输出 sentence_info。
5. 对 sentence 做时间归一化。

统一 ASR schema：

```json
{
  "segment_id": 1,
  "asr_model": "paraformer-zh+fsmn-vad+ct-punc+cam++",
  "language": "zh",
  "sentences": [
    {
      "start_ms": 1200,
      "end_ms": 4300,
      "text": "这里演示的是订单审批流程。",
      "speaker": "SPEAKER_00",
      "confidence": 0.91,
      "tokens": []
    }
  ],
  "hotwords_used": ["华世王镞", "订单审批"],
  "quality_flags": []
}
```

落库：

- `kb_video_segments.transcript`
- `kb_video_segments.speaker_info_json`
- `kb_raw_data`：`source_type='asr'`，`round=1`

### Stage 4：抽帧

第一版每个 segment 抽：

- start frame
- middle frame
- end frame
- 若 segment > 45 秒，追加均匀 2-3 帧
- 对屏幕录制/PPT 类视频，可 1 fps 低频抽帧后做 OCR 去重

落库：

- frame references：不要直接塞大二进制进 DB。
- keyframe paths/resource refs 存 JSON。
- `frame_times_json` 保存 frame_time、frame_index、storage_ref、hash。

### Stage 5：OCR

对抽样帧运行 PaddleOCR。

输出结构：

```json
{
  "frame_time_ms": 15300,
  "items": [
    {
      "text": "订单审批",
      "box": [[10,20],[200,20],[200,60],[10,60]],
      "confidence": 0.96
    }
  ]
}
```

去重策略：

- 同一 segment 内完全相同文本合并。
- 相邻 segment 若 OCR 主体相似度 > 0.92，可标记为 repeated，不重复计入摘要。
- 字幕类短文本按时间保留；PPT 标题类文本按 slide/scene 保留。

落库：

- `kb_video_segments.ocr_text`
- `kb_raw_data`：`source_type='ocr'`，`round=2`
- 详细 box 坐标放 metadata。

### Stage 6：VLM 视觉描述

第一版建议：

- 默认 Qwen2.5-VL / Qwen-VL。
- 成本受限时，先 MiniCPM-V 生成粗 caption，高价值或低置信度 segment 再 Qwen。

输入：

- segment 时间范围。
- 抽样帧或短 clip。
- frame timestamp list。
- OCR 文本可作为上下文提供，但要标记为 OCR evidence。

输出 schema：

```json
{
  "segment_summary": "该片段展示订单审批系统的列表页，讲解如何筛选待审批订单。",
  "timeline": [
    {
      "start_ms": 0,
      "end_ms": 15000,
      "event": "讲解人打开订单审批列表。",
      "visible_text": ["订单审批", "待审批"],
      "entities": ["订单审批系统"],
      "evidence_frame_times_ms": [0, 15000],
      "confidence": 0.86
    }
  ],
  "key_terms": ["订单审批", "待审批", "筛选"],
  "uncertainties": []
}
```

落库：

- `kb_video_segments.caption`
- `kb_raw_data`：`source_type='vision'`，`round=3`

### Stage 7：融合为 segment content_text

融合输入：

- ASR transcript
- OCR visible text
- VLM caption/timeline
- 文件名/目录/用户标签

融合输出：

- `title`
- `summary`
- `content_text`
- `entities`
- `events`
- `tags`
- `quality_flags`

推荐 `content_text` 模板：

```text
【视频片段】00:01:20-00:01:50
【摘要】该片段讲解订单审批系统中的待审批列表筛选。
【画面文字】订单审批；待审批；筛选条件；提交人
【语音转写】这里我们进入订单审批页面，先选择待审批状态...
【视觉描述】画面显示后台管理系统表格，讲解人演示筛选操作。
【实体】订单审批系统；待审批订单；提交人
```

这段文本进入 embedding 与 FTS，是第一版检索主干。

### Stage 8：向量化与全文索引

第一版：

- 使用当前 BGE-M3 embedding endpoint。
- 写入 `kb_chunks.embedding vector(1024)` 或新增 `kb_segment_embeddings.embedding vector(1024)`。
- 同时建立 FTS：PostgreSQL `tsvector` + GIN。

检索：

1. Dense vector top_k。
2. FTS top_k。
3. RRF 融合。
4. 可选 BGE reranker。
5. 返回 segment citation。

### Stage 9：结果引用与播放器跳转

每个搜索结果必须包含：

```json
{
  "document_id": 123,
  "asset_id": 10,
  "segment_id": 45,
  "start_ms": 80000,
  "end_ms": 110000,
  "snippet": "...",
  "evidence": {
    "transcript": [...],
    "ocr": [...],
    "frames": [...]
  }
}
```

前端点击后应能：

- 打开视频文档。
- 跳转到 `start_ms`。
- 展示 transcript/OCR/caption 证据。

## 5. 建议数据表

### 5.1 `kb_media_assets`

一行代表一个视频/音频/图片媒体资产。

```sql
CREATE TABLE kb_media_assets (
  id BIGSERIAL PRIMARY KEY,
  owner_id INTEGER NOT NULL,
  document_id BIGINT NOT NULL,
  file_id BIGINT NOT NULL,
  media_type VARCHAR(32) NOT NULL, -- video/audio/image
  filename VARCHAR(512) NOT NULL,
  mime_type VARCHAR(128) DEFAULT '',
  duration_ms BIGINT,
  width INTEGER,
  height INTEGER,
  fps DOUBLE PRECISION,
  frame_count BIGINT,
  video_codec VARCHAR(64),
  audio_codec VARCHAR(64),
  has_video BOOLEAN DEFAULT FALSE,
  has_audio BOOLEAN DEFAULT FALSE,
  checksum VARCHAR(64),
  probe_status VARCHAR(32) DEFAULT 'pending',
  pipeline_status VARCHAR(32) DEFAULT 'pending',
  metadata_json JSONB,
  error_message TEXT,
  created_at TIMESTAMPTZ DEFAULT now(),
  updated_at TIMESTAMPTZ DEFAULT now()
);
```

索引：

```sql
CREATE INDEX ix_kb_media_assets_owner ON kb_media_assets(owner_id);
CREATE INDEX ix_kb_media_assets_document ON kb_media_assets(document_id);
CREATE INDEX ix_kb_media_assets_file ON kb_media_assets(file_id);
```

### 5.2 `kb_video_segments`

视频检索与引用的核心表。

```sql
CREATE TABLE kb_video_segments (
  id BIGSERIAL PRIMARY KEY,
  owner_id INTEGER NOT NULL,
  document_id BIGINT NOT NULL,
  asset_id BIGINT NOT NULL,
  segment_index INTEGER NOT NULL,
  start_ms BIGINT NOT NULL,
  end_ms BIGINT NOT NULL,
  duration_ms BIGINT NOT NULL,
  boundary_source VARCHAR(32) DEFAULT 'fixed_time',
  title VARCHAR(512),
  summary TEXT,
  transcript TEXT,
  ocr_text TEXT,
  caption TEXT,
  content_text TEXT NOT NULL DEFAULT '',
  language VARCHAR(32),
  speaker_info_json JSONB,
  frame_refs_json JSONB,
  evidence_json JSONB,
  entities_json JSONB,
  events_json JSONB,
  tags_json JSONB,
  quality_flags_json JSONB,
  status VARCHAR(32) DEFAULT 'pending',
  error_message TEXT,
  created_at TIMESTAMPTZ DEFAULT now(),
  updated_at TIMESTAMPTZ DEFAULT now(),
  UNIQUE(asset_id, segment_index)
);
```

索引：

```sql
CREATE INDEX ix_kb_video_segments_owner ON kb_video_segments(owner_id);
CREATE INDEX ix_kb_video_segments_document ON kb_video_segments(document_id);
CREATE INDEX ix_kb_video_segments_asset_time ON kb_video_segments(asset_id, start_ms, end_ms);
CREATE INDEX ix_kb_video_segments_status ON kb_video_segments(status);
```

如果使用 PostgreSQL FTS：

```sql
ALTER TABLE kb_video_segments
  ADD COLUMN content_tsv tsvector GENERATED ALWAYS AS (
    to_tsvector('simple', coalesce(content_text, ''))
  ) STORED;

CREATE INDEX ix_kb_video_segments_content_tsv
  ON kb_video_segments USING GIN(content_tsv);
```

中文分词如果后续需要更好效果，可再评估 `zhparser` 或应用层关键词字段。

### 5.3 `kb_segment_embeddings`

如果只使用 BGE-M3 text embedding，也可以先复用 `kb_chunks`。但为了多模态扩展，建议新增独立表。

```sql
CREATE TABLE kb_segment_embeddings (
  id BIGSERIAL PRIMARY KEY,
  owner_id INTEGER NOT NULL,
  document_id BIGINT NOT NULL,
  asset_id BIGINT NOT NULL,
  segment_id BIGINT NOT NULL,
  embedding_kind VARCHAR(32) NOT NULL, -- text_dense / visual_dense / keyframe_dense
  model_name VARCHAR(128) NOT NULL,
  model_dim INTEGER NOT NULL,
  content_hash VARCHAR(64) NOT NULL,
  embedding vector(1024),
  metadata_json JSONB,
  created_at TIMESTAMPTZ DEFAULT now(),
  updated_at TIMESTAMPTZ DEFAULT now(),
  UNIQUE(segment_id, embedding_kind, model_name, content_hash)
);
```

索引：

```sql
CREATE INDEX ix_kb_segment_embeddings_segment
  ON kb_segment_embeddings(segment_id);

CREATE INDEX ix_kb_segment_embeddings_asset_kind
  ON kb_segment_embeddings(asset_id, embedding_kind);

CREATE INDEX ix_kb_segment_embeddings_text_hnsw
  ON kb_segment_embeddings
  USING hnsw (embedding vector_cosine_ops)
  WITH (m = 16, ef_construction = 200)
  WHERE embedding_kind = 'text_dense' AND model_dim = 1024;
```

注意：pgvector 同一列维度固定。若后续引入 768 维 OpenCLIP，不能混进 `vector(1024)`。可选策略：

1. 统一选择 1024 维模型，例如 BGE-M3、Visualized-BGE-M3、ImageBind 类方案。
2. 新增 `embedding_768 vector(768)`。
3. 为不同维度建不同表。

### 5.4 `kb_media_stage_runs`

为了多 worker 和断点诊断，建议对每个 asset/segment/stage 建阶段账本。

```sql
CREATE TABLE kb_media_stage_runs (
  id BIGSERIAL PRIMARY KEY,
  owner_id INTEGER NOT NULL,
  document_id BIGINT NOT NULL,
  asset_id BIGINT NOT NULL,
  segment_id BIGINT,
  stage VARCHAR(64) NOT NULL,
  status VARCHAR(32) NOT NULL DEFAULT 'pending',
  attempt INTEGER DEFAULT 0,
  worker_id VARCHAR(64),
  started_at TIMESTAMPTZ,
  finished_at TIMESTAMPTZ,
  duration_ms INTEGER,
  input_hash VARCHAR(64),
  output_hash VARCHAR(64),
  model_used VARCHAR(128),
  prompt_hash VARCHAR(64),
  diagnostics_json JSONB,
  error_message TEXT,
  created_at TIMESTAMPTZ DEFAULT now(),
  updated_at TIMESTAMPTZ DEFAULT now()
);
```

stage 枚举建议：

- `probe`
- `segment`
- `audio_extract`
- `asr`
- `frame_sample`
- `ocr`
- `vlm_caption`
- `fusion`
- `embedding`
- `graph_extract`
- `relation_build`

## 6. 与现有 `kb_raw_data` / `kb_page_fusions` 的关系

当前 `kb_raw_data` 是按 `page` 组织的原始多轮采集结果。视频没有自然页，所以建议：

- 第一版继续把 `page` 当成 `segment_index + 1` 使用，保持兼容。
- `source_type` 扩展为：`asr`、`ocr`、`vision`、`media_probe`、`fusion`。
- `metadata_json` 存 `segment_id/start_ms/end_ms/frame_refs`。

示例：

```json
{
  "segment_id": 45,
  "start_ms": 80000,
  "end_ms": 110000,
  "evidence_type": "asr_sentence",
  "sentences": [...]
}
```

`kb_page_fusions` 可以在第一版中暂不复用，或把 page fusion 语义扩展成 segment fusion：

- `page = segment_index + 1`
- `fused_text = segment content_text`
- `body_json` 存 segment schema
- `evidence_json` 指向 `kb_raw_data`

更干净的长期方案是新增 `kb_video_segments`，让 page_fusions 只服务文档页，video_segments 服务视频段。

## 7. 检索方案

## 7.1 第一版：文本混合检索

查询流程：

1. 用户输入 query。
2. 调 BGE-M3 embedding。
3. Dense recall：查 `kb_segment_embeddings` 或 `kb_chunks`。
4. Lexical recall：查 `kb_video_segments.content_tsv`。
5. RRF 融合。
6. 调 reranker 对 top 50/100 重排。
7. 返回 segment citation。

RRF：

```text
score = Σ 1 / (k + rank_i)
k 默认 60
```

优点：

- 不依赖不同召回分数可比。
- dense、FTS、未来 graph/visual 都能加。

## 7.2 第二版：视觉检索

场景：

- “找出现某个界面的片段”
- “找包含某类产品/设备/场景的视频”
- 用户上传一张截图找对应视频位置

方案：

- keyframe embedding。
- text-to-image 或 image-to-image 检索。
- 首选 Visualized-BGE-M3（中文友好、1024 维）。
- 备选 OpenCLIP。

## 7.3 第三版：视频 GraphRAG

适合：

- “哪些视频讲过 A 产品和 B 流程的关系？”
- “按业务流程总结所有培训视频。”
- “这个客户问题在哪些会议里被反复提到？”

方案：

1. 从 segment content_text 抽 entity/event/claim。
2. 建 segment -> entity -> relation 证据链。
3. 对 entity description 和 community report 做 embedding。
4. 先 local graph search，后 community/global search。

## 8. 前端体验建议

### 8.1 视频资料详情页

在现有 knowledge reader 中增加 video 模式：

- 左侧：视频播放器。
- 右侧：分析面板。
- 下方：时间线/片段列表。

每个 segment 显示：

- 时间范围。
- 摘要。
- transcript。
- OCR 文本。
- 关键帧缩略图。
- 实体/标签。
- 置信度和质量标记。

### 8.2 搜索结果

视频结果与普通 chunk 结果区分显示：

```text
[视频片段] 订单审批培训.mp4  00:01:20 - 00:01:50
摘要：讲解如何筛选待审批订单...
证据：语音转写 + 屏幕文字 + 关键帧
按钮：播放该片段 / 查看上下文 / 问 AI
```

### 8.3 进度展示

视频分析比文档慢，必须展示阶段进度：

- 媒体探测
- 分段
- 音频转写
- 抽帧
- OCR
- 视觉理解
- 融合
- 向量化
- 图谱

失败时展示：

- 哪个 stage 失败。
- 是否可重试。
- 已完成哪些结果。
- 失败原因摘要。

## 9. 模型路由与成本策略

### 9.1 默认生产路由

| 阶段 | 默认模型/工具 | fallback |
|---|---|---|
| probe | PyAV / ffprobe | decord metadata |
| segment | fixed 30s + PySceneDetect optional | fixed 30s |
| frame sample | decord | PyAV |
| ASR | FunASR paraformer-zh + fsmn-vad + ct-punc + cam++ | SenseVoiceSmall / faster-whisper |
| OCR | PaddleOCR | VLM OCR |
| VLM caption | Qwen2.5-VL 7B/32B | MiniCPM-V 4.6 |
| embedding | BGE-M3 | 当前 embedding fallback chain |
| rerank | BGE reranker | 无 rerank 直接返回 |

### 9.2 分级处理

为了控制成本，建议三档：

#### fast

- 只做 ASR + 关键帧 OCR。
- 不做 VLM 或只用 MiniCPM。
- 适合大量普通会议/内部资料初筛。

#### balanced（默认）

- ASR + OCR + Qwen 对关键 segment 做视觉描述。
- fixed segment + 可选 scene 修正。
- 建 text embedding + FTS。

#### premium

- 更密集抽帧。
- Qwen 全 segment。
- 视觉 embedding。
- 图谱抽取。
- 适合高价值培训课、产品资料、客户访谈。

### 9.3 缓存与幂等

所有阶段输入都应有 hash：

- file checksum
- segment time range
- frame hash list
- transcript hash
- prompt hash
- model version

同样输入 + 同样模型 + 同样 prompt，不重复调用模型。

## 10. 质量评估与验收标准

### 10.1 基准测试集

准备 20-50 个真实或脱敏视频：

| 类型 | 数量 | 重点 |
|---|---:|---|
| 会议录音/视频 | 5-10 | 多人说话、重叠、噪声。 |
| 培训课/PPT | 5-10 | PPT OCR、章节、术语。 |
| 屏幕录制/系统演示 | 5-10 | UI OCR、操作流程、时间线。 |
| 产品/现场拍摄 | 3-5 | 视觉描述、对象识别。 |
| 中英混合/方言口音 | 3-5 | ASR 鲁棒性。 |
| 无音频/无画面异常文件 | 3-5 | 降级与错误处理。 |

### 10.2 指标

ASR：

- CER/WER。
- 企业术语召回率。
- 时间戳漂移。
- speaker purity。
- real-time factor。

OCR：

- 屏幕/PPT 标题召回。
- 重复文本去重率。
- 坐标准确度抽查。

VLM：

- segment summary 准确性。
- hallucination rate。
- JSON 合法率。
- 事件时间线准确性。

检索：

- Recall@5/10。
- MRR。
- 点击后时间点是否正确。
- 回答引用是否能落回 transcript/OCR/frame。

系统：

- 单小时视频处理耗时。
- GPU/CPU/RAM 峰值。
- 队列失败率。
- 重试成功率。
- 脏数据清理率。

## 11. 分阶段实施计划

### Phase 0：设计与表结构

产物：

- `kb_media_assets`
- `kb_video_segments`
- `kb_media_stage_runs`
- 可选 `kb_segment_embeddings`
- README 更新
- sandbox 最小验收样例

验收：

- migration/init_db 可建表。
- 空库启动无报错。
- 单测覆盖模型字段与阶段状态。

### Phase 1：音频优先的视频入库

范围：

- 支持 mp4/mov/mkv/webm + mp3/wav/m4a。
- probe。
- fixed 30s segment。
- FunASR transcript。
- segment content_text。
- BGE-M3 embedding。
- 搜索返回 timestamp。

这是最小可用闭环。

### Phase 2：关键帧 + OCR

范围：

- decord 抽帧。
- PaddleOCR。
- OCR 去重。
- transcript + OCR 融合。
- 前端显示关键帧与 OCR 证据。

### Phase 3：VLM segment caption

范围：

- Qwen2.5-VL 能力接入。
- MiniCPM fallback。
- JSON schema validation + repair。
- VLM 结果进入融合。

### Phase 4：混合检索与重排

范围：

- pgvector + FTS + RRF。
- reranker topN。
- 返回证据链。

### Phase 5：视觉检索

范围：

- keyframe embedding。
- Visualized-BGE-M3 或 OpenCLIP。
- image query -> video segment。

### Phase 6：GraphRAG

范围：

- segment entity/event/claim。
- graph expansion。
- video library community report。

## 12. 最具体的第一批任务拆分

### 任务 A：视频媒体 schema 与状态账本

修改范围：`modules/knowledge/`

- 新增模型：`KbMediaAsset`、`KbVideoSegment`、`KbMediaStageRun`。
- `init_db.py` 建表。
- stage 状态服务：create/update/list。
- 文档 README 更新。

验收：

- `mcp run_test modules/knowledge/...`
- `probe /api/health`
- DB schema 查到三张表。

### 任务 B：媒体 probe service

- 输入 `document_id`。
- 经授权获取 file path。
- PyAV probe。
- 写 `kb_media_assets`。
- 失败记录 stage run。

验收：

- 用一个短 mp4 测出 duration/fps/codec。
- 无音频视频不失败。
- 坏文件状态为 failed，不假绿。

### 任务 C：fixed segment service

- 按 duration 生成 segment。
- 幂等：重复运行不重复创建。
- 支持 force rebuild。

验收：

- 95 秒视频生成 4 段：0-30、30-60、60-90、90-95。
- 重新运行不重复。

### 任务 D：ASR adapter

第一版可以先封装外部服务/本地命令接口，不把 FunASR 重依赖直接塞进主后端环境。

建议：

- `media_asr_service.py` 定义统一接口。
- `FunAsrAdapter` 可配置 endpoint 或 local python。
- 输出统一 schema。

验收：

- 短中文音频返回 transcript。
- speaker 可为空但字段存在。
- 错误可诊断。

### 任务 E：segment content_text + embedding

- 将 transcript 写入 content_text。
- 复用现有 embedding service。
- 可先写入 `kb_chunks`：`block_type='video_segment'`，`page=segment_index+1`，`resource_ref=segment_id`。
- 或写入 `kb_segment_embeddings`。

建议第一版：

- 为减少检索改动，先写 `kb_chunks`。
- 同时保留 `kb_video_segments` 作为引用 metadata。
- 后续再拆专用 embedding 表。

验收：

- 搜索关键词能命中视频 segment。
- 返回结果能带 start_ms/end_ms。

### 任务 F：前端最小展示

- video document detail。
- segment list。
- 搜索结果跳转。
- 进度阶段显示。

验收：

- 上传视频后能看到分析阶段。
- 搜索后点击结果打开视频指定时间。

## 13. 风险与规避

| 风险 | 规避 |
|---|---|
| 视频处理很慢导致用户以为卡死 | stage run + 前端进度 + partial result。 |
| 多 worker 重复处理同一视频 | DB stage lock / task id / input hash。 |
| 模型输出 JSON 不合法 | JSON schema 校验 + repair + fallback。 |
| 大视频占满磁盘 | 抽帧/音频临时文件统一工作目录，完成后清理；只保存必要 keyframe。 |
| OCR/VLM 结果重复 | hash + 相似度去重 + segment 内合并。 |
| ASR diarization 被误解为身份 | UI 标注“说话人1/2”，不显示真实姓名，身份识别另做。 |
| 视觉模型幻觉 | 必须保留 evidence_frame_times 和 confidence，回答引用回源。 |
| embedding 维度混乱 | model_dim + embedding_kind 强约束，不同维度分表/分列。 |
| 许可证风险 | YOLO/部分模型商用许可单独审查，第一版可不依赖 AGPL 项目。 |
| 框架边界被打破 | 所有视频能力放 knowledge，跨模块调用走 capability，模型公共能力另开框架任务。 |

## 14. 最终推荐

最适合我们项目的落地路线是：

1. **先做音频转写 + segment text RAG**：这是最快闭环，也是企业知识库最常用价值点。
2. **再加关键帧 OCR**：对培训、PPT、系统演示类视频价值极高。
3. **再加 Qwen2.5-VL segment caption**：把画面动作、界面变化、实体、事件结构化。
4. **检索上坚持 PostgreSQL + pgvector + FTS + RRF + reranker**：不引入额外向量数据库，复用当前 BGE-M3 基础设施。
5. **GraphRAG 放在第三阶段以后**：当 segment 数据稳定后，再抽 entity/event/claim，做跨视频知识网络。
6. **模型选择上 FunASR + Qwen 为主，MiniCPM 为 fallback，LLaVA 只做研究基线**。

第一版做到以下结果就算成功：

```text
上传视频 → 自动登记 → 探测时长 → 切 30 秒 segment → ASR 转写 → 生成 segment content_text → BGE-M3 向量化 → 搜索命中 → 点击跳到视频时间点 → 能看到 transcript 证据
```

这个闭环与当前 knowledge 模块最贴合，风险最低，后续 OCR、VLM、视觉 embedding、GraphRAG 都能自然叠加。
