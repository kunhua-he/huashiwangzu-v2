# 知识库后台任务统一调度目标架构

## 先看图

```text
[用户上传 / 点重试 / 系统补任务]
                 |
                 v
        [发布器：数据库写一条任务]
                 |
                 v
          [任务表：等待被处理]
                 |
                 v
 [唯一分配器：看任务多少、机器忙不忙、云端额度]
                 |
                 v
       [发出一个单任务执行进程]
                 |
                 v
       [先查：这个步骤以前做完了吗？]
           | 是                    | 否
           v                       v
       [记录已完成]              [真正执行]
           \                       /
            v                     v
          [结果、进度、产物全部写回数据库]
                              |
                              v
                 [分配器判断并安排下一个步骤]
```

用最直白的话说：入口只负责把任务放进数据库；只有分配器决定谁来做；每个执行进程只做一件事，做完就退出；数据库永远知道任务走到哪一步。重复点击、程序中断、机器过载都回到数据库重新判断，不靠某个进程记住。

## 进程暴毙和资源账，先看图

```text
[分配器发出任务] -> [执行进程 PID=1234]
                           |
                     每 5 秒上报
                           v
              [任务表：心跳、租约、PID]
                           |
              +------------+------------+
              |                         |
         心跳正常                    心跳消失 / PID 消失
              |                         |
              v                         v
        [继续运行]          [旧租约作废 -> 任务回数据库]
                                        |
                                        v
                              [重新分配一次新的执行进程]
```

```text
[每个执行进程]
  -> 记录自己的 CPU 时间、内存峰值、GPU 显存、磁盘 I/O
  -> 写入“这一次任务实际消耗多少”
  -> 分配器用这些历史数据计算“机器还够不够再开一个”
```

这里说的“线程暴毙”在最终实现中指单任务**执行进程**退出、被系统杀死或失去响应。这样即使某个解析器、Python 扩展或模型调用把自己弄挂，也只损失一条任务，不会拖死整个调度器。

## 当前落地状态（2026-07-11）

```text
所有发布入口 -> publish_task() -> 同一张 framework_system_task_queues
                                      |
                                      v
task_worker_main（唯一 Dispatcher） -> lease/资源判断 -> 单任务 executor 进程
                                      |
                                      v
知识库独立 stage .py -> 阶段账本 -> Dispatcher 结算回调 -> 后继任务
```

- 已落地 `backend/app/services/task_dispatcher.py`：固定信封、唯一 leader、lease/heartbeat/fencing、短命 executor、进程资源账、暂停释放、缺失或过期租约恢复和低频 reconciliation。
- `backend/app/services/task_worker.py` 已收敛为**任务 handler 注册表**，没有领取、轮询、lane、扩缩容或超时回收循环；不能形成第二控制器。
- `backend/app/services/task_handler_bootstrap.py` 是 Dispatcher 与 executor 的轻量启动入口：只注册持久任务 handler、知识库解析器能力及其必要依赖；不会构造 FastAPI 或导入全量 HTTP 路由、桌面和代码索引模块。维护时可用 `TASK_DISPATCHER_ALLOWED_DOCUMENT_IDS` 临时隔离指定文档领取，默认不启用。
- `scripts/backend_watchdog.sh` 只守护一个 web 进程组和一个 Dispatcher；它不再按 pending 数拉 20 个 worker。
- `modules/knowledge/backend/services/pipeline_stages/` 已有 11 个独立节点文件。阶段本身只执行/复用；DAG 后继由 Dispatcher 的 fenced settlement callback 发布。
- `kb_pipeline_autofill` 已不再是队列 handler；不完整文档修复作为 Dispatcher 的低频 reconciliation 执行。
- 所有新的 `SystemTaskQueue` 创建点已收敛到 `publish_task()`；发布器拒绝 `physical_path`、`file_path` 等物理路径字段。企业导入文件任务只传 `source_manifest_id`，物理路径只保存在模块自己的清单表中。
- 已建立 `uq_framework_kb_active_stage` 部分唯一索引，保证同一文档同一 stage 最多一条 `pending/running` 知识库任务。

### 已完成实测

已用带 `DISPATCHER_FULL_SUCCESS_*` 标记的一页 PDF 执行真实上传、`file_id` 权限检查、发布、Dispatcher claim、独立 executor 子进程和永久清理。11 个节点均实际执行并回写 `completed`：`source_validate`、`parse_index`、`raw_text`、`page_render`、`raw_ocr`、`raw_vision`、`fusion`、`profile`、`cognitive_index`、`graph`、`relations`；最终文档的 parse/vector/raw/fusion/profile/graph/relation 状态全部为 `done`。测试文件、可执行任务行和回收站记录均已永久删除。

在修复 executor 全量路由启动后，又以隔离的 `DISPATCHER_LIGHT_BOOT_E2E` PDF 重跑上述 11 节点。每条阶段任务均通过轻量启动器拉起独立进程并完成；资源账记录的峰值 RSS 为约 `181–227 MiB`（页面渲染与视觉阶段最高约 `227 MiB`），不再出现此前全量启动造成的多 GiB 常驻内存。测试结束后已恢复高成本节点暂停策略并清理测试记录。

云端端点还额外进行了 20 路并发探测：LLM `20/20` 成功（总墙钟约 3.9 秒）；VLM `20/20` 成功（总墙钟约 6.8 秒）。试跑发现并修复了视觉网关把成功 Responses payload 中的 `"error": null` 误当失败的问题。常规 JSON 配置没有因此提高到 20：生产默认仍是保守的 LLM/VLM 各 4 个并发；扩大额度必须由维护者明确修改 `dispatcher.provider_limits` 后生效。

2026-07-11 再次使用当前 `gpt-5.5-knowledge` 与 `gpt-5.5-vision` 配置进行真实云端并发探测：LLM `20/20` 成功（约 `4.14` 秒），VLM `20/20` 成功（约 `7.13` 秒）；VLM 使用 Pillow 生成的标准 RGB PNG，全部命中主 profile、无 fallback、无接口错误。随后按可用额度升级到 40 路：LLM `40/40` 成功（约 `8.03` 秒），VLM `40/40` 成功（约 `11.60` 秒），仍无 fallback 或接口错误。并发探测绕过 Dispatcher 的生产 provider 限额，仅用于验证云端端点；生产任务当前已在 JSON 中设为 LLM/VLM 各 40 路、总 executor 48 路，仍受本机资源阈值保护。

高并发消化历史图谱债务时发现图谱节点的实际工作量可超过通用 20 分钟任务上限，因此 Dispatcher 已改为读取 JSON 的 `dispatcher.stage_timeouts_seconds`。图谱节点当前为 `3600` 秒，其他阶段仍按更短的工作量上限执行；任务领取时会把阶段级上限写入 executor lease，避免健康但仍在处理的图谱任务被通用超时错误终止。

## 重构前基线：已核对并已纠正的事实

以下是当前代码和 live snapshot 的事实，不是目标设计：

| 当前位置 | 已有能力 | 当前限制或缺口 |
|---|---|---|
| `framework_system_task_queues` 与 `backend/app/models/system.py` | 已有 `task_type`、`parameters`、状态、优先级、重试、`document_id`、`stage_key`、`lane_key`、`ready_status`、依赖键和调度索引。`ensure_framework_scheduling_columns()` 已用 advisory lock 做增列/索引。 | 没有 lease token、lease owner、过期时间、心跳、attempt 资源记录或统一的固定任务信封。 |
| `backend/app/services/task_worker.py` | 已有 PostgreSQL `FOR UPDATE SKIP LOCKED` 领取、stage/lane 统计、公平加权、暂停、超时回收、handler 注册和 worker RSS 退休。 | 每个 lane 自己轮询并领取；资源判断主要是静态 JSON 并发和 worker 组 RSS，不知道单任务 CPU/GPU/RSS/I/O，也没有栅栏令牌防旧 worker 回写。 |
| `backend/app/task_worker_main.py` 与 `scripts/backend_watchdog.sh` | watchdog 以 `TASK_WORKER_AUTOSTART=0` 启动 web，再按 pending 数动态拉起 `app.task_worker_main`。 | 当前配置为最多 20 个 worker 进程、每进程 10 个 async lane；这是多进程自抢，不是唯一分配器。 |
| `backend/data/config/task_worker.json` | 已有 local/vision/LLM/derived/relation lane、stage 顺序、暂停和动态公平参数。 | `raw_ocr`、`raw_vision`、`fusion`、`profile`、`graph` 目前均配置为 paused；并发上限 160 不能代表真实本机资源或云端额度。 |
| `modules/knowledge/backend/services/pipeline_service.py` | 已有一阶段一队列行、源文件检查、阶段短路、stage run、artifact ledger 和 DAG 后继逻辑。 | `_pipeline_stage_handler` 同时做执行、记录和直接 `_enqueue_successors`；节点并非独立文件。当前 artifact `input_hash` 含 task/run 标识，只能追踪本次运行，不能作为跨重试稳定缓存键。 |
| `modules/knowledge/backend/services/pipeline_autofill_service.py` | 已有每小时补排不完整文档和失败任务的治理能力。 | 它自己注册 `kb_pipeline_autofill` 并写队列，是当前第二个补排控制循环。 |
| `backend/app/services/event_bus.py` 与 `framework_event_log` | 已有持久事件、失败重试和 `SKIP LOCKED` 重放。 | `emit_module_event()` 现在用独立 session 先写事件再同步调用 handler，不与知识库阶段结果同一事务；不能原样当作阶段结算事件箱。 |
| `modules/knowledge/backend/services/model_routing.py` | 已有进程内 LLM/VLM 调用 limiter、模型降级和自动暂停。 | limiter 是单 worker 进程内计数；在多 worker 情况下不是全局云端配额。 |

当前 live snapshot 的直接结论是：`3532` 条 ready 任务中 `3531` 条被暂停配置阻塞，其中 `graph` 为 `3517` 条；并不是 CPU 算法没有继续放线程。最近指标显示 profile/graph 的中位时长约 70 到 76 秒，而数据库写入通常是毫秒级，所以云端 provider 配额和失败熔断必须独立于本机 CPU 预算。

## 本次重构目标

这次不是给知识库“调几个并发数”，而是在不改变知识库业务产物和既有 API 外形的前提下，把后台任务的控制权收回数据库和唯一 Dispatcher。

1. **一个控制面**：`framework_system_task_queues` 中所有 task type 只由一个 Dispatcher Leader 领取。旧的多进程多 lane 自抢和 `kb_pipeline_autofill` 独立补排不再可执行。
2. **一个固定入口**：所有任务发布都经过统一校验信封；现有 `parameters` 仍是唯一持久载体，但结构固定。知识库通过 `file_id` 进行访问检查和临时路径解析，不把物理路径当任务输入。
3. **一次任务可追溯**：每一次 attempt 都有 lease、心跳、PID、失败类别、资源账和可拒绝的旧 lease token。任何执行进程暴毙或机器重启后，任务能够从数据库恢复。
4. **阶段不重复做**：保留当前源文件检查、文档阶段状态和产物账本；补足不含 task/run 标识的稳定输入 hash，使相同输入的重试和重复发布可以安全复用结果。
5. **资源按任务算**：本地 CPU、内存、GPU/显存、数据库/解析器容量和云端 provider/model 额度分别计算；没有任何“CPU 低于 80% 就无限开线程”的路径。
6. **状态不再说谎**：用户和运维能区分 waiting dependency、paused、ready、running、retrying、skipped、degraded、failed；当前被暂停的 graph/LLM backlog 必须明确显示为 paused，而不是“排队但不动”。
7. **保持现有业务能力**：知识库现有 `kb_pipeline_stage` DAG、阶段产物、文档状态、能力接口和模块边界保留；其他模块既有 handler 通过适配接入，而不是重写业务功能。

## 定位

本文是知识库后台管道的唯一目标架构规范，同时定义共享任务平台的替换边界。切换完成后，Dispatcher 取代当前多 worker 自行抢占任务的控制面。后续实现必须遵守本文；知识库的局部便利需求不得绕开或扩展本文定义的框架契约。

## 核心决定

系统只有一个持久任务队列、一个调度控制面，以及完成单任务即退出的执行单元。

```text
知识库/API 入口
  -> 任务发布器
  -> framework_system_task_queues
  -> Dispatcher Leader
  -> 原子领取并发放租约
  -> 单任务执行单元
  -> 产物 + 阶段结果 + 事件日志同一事务提交
  -> Dispatcher 被唤醒并评估 DAG
```

- PostgreSQL 是任务状态、租约、尝试次数、资源观测和调度决策的唯一权威。
- `framework_system_task_queues` 是唯一可执行队列，且 Dispatcher 领取其中的所有 task type。禁止增加第二张业务队列表、内存队列或进程内任务列表。
- 一个 Dispatcher Leader 独占配额计算与任务分配。执行单元不得自行选择下一个任务；知识库阶段代码不得直接投递下游任务。
- 一个执行单元只处理一条已领取任务，持久化结果后退出。CPU 或原生库任务使用进程而不是 Python 线程；云端 I/O 可以在该进程内使用受限 async。独立管理的本地模型服务是唯一允许长期存活的模型进程。
- 新旧控制面绝不同时领取同一队列。切换采用本文规定的一次维护窗口纪律。

保留现有知识库阶段账本、产物表、文档状态字段、统一队列表、PostgreSQL advisory lock 和 `FOR UPDATE SKIP LOCKED` 原子领取模式。现有多 worker 公平抢占循环和 `_worker_lane_loop` 不再作为任何 task type 的控制面保留。

## 适用范围与兼容方式

当前 `framework_system_task_queues` 是平台共享表，`task_worker` 会按注册 handler 领取任务，并非知识库专用。因此只改知识库而让旧 worker 继续扫同一张表，必然形成双控制面，不能接受。

- 一次切换后，Dispatcher 是共享队列表的唯一领取者，旧 task worker 不再运行。
- 每个 task type 注册一份 `TaskDefinition`：任务信封校验器、lane、资源画像、超时、重试策略和执行适配器。
- 非知识库的既有 handler 不需要重写业务逻辑。它们通过通用适配器作为“无 DAG 的单节点任务”执行，并以同一租约、资源预算和事件结算协议运行。
- `kb_pipeline_stage` 是其中带 DAG、产物复用和文档状态的任务类型；它不拥有另一套队列或另一台 Dispatcher。
- 任何尚未声明 `TaskDefinition` 的旧 task type 都不允许在切换后领取。发布器必须拒绝它，而不能静默回落到旧 worker。

## 边界

这是框架与知识库模块共同完成的一项架构变更。

- 框架负责队列、Dispatcher、租约协议、执行进程生命周期、资源采集、唤醒通知、事件日志和通用观测，代码位于 `backend/`，数据位于 `framework_*`。
- 知识库负责 DAG 声明、阶段执行器、`kb_*` 产物、阶段运行账本、文档阶段状态和知识库视图，代码位于 `modules/knowledge/`，数据位于 `kb_*`。
- 知识库不得把物理文件路径作为外部传入的任务契约。任何内容读取先使用 `file_id` 和任务所属用户/系统主体执行框架文件访问检查；解析出的路径只在当前执行单元中短暂存在。

## 固定任务契约

所有落入统一队列的工作先通过共享信封发布，再携带经过 task type 校验的 `body`。知识库的 ingest、重试、重跑、回填和后继节点统一使用 `task_type=kb_pipeline_stage`，不能为不同阶段重新创建不同队列类型。

```json
{
  "schema_version": 1,
  "task_type": "kb_pipeline_stage",
  "module": "knowledge",
  "owner_id": 7,
  "lane_key": "llm_analysis",
  "requested_by": "user:7",
  "trigger": "ingest|retry|rerun|backfill",
  "body": {
    "document_id": 123,
    "file_id": 456,
    "stage_key": "fusion",
    "pipeline_run_id": 789,
    "source_revision": "file-md5-or-version",
    "input_hash": "deterministic-stage-input-hash"
  }
}
```

规则：

- 所有任务必须具备共享字段；`body` 由各自 `TaskDefinition` 校验。知识库任务还必须具备 `document_id`、`file_id`、`stage_key`、`source_revision` 和 `input_hash`。
- 现有 `framework_system_task_queues.parameters` 是唯一持久任务载体，内容固定为通过发布器校验的 JSON 信封。不得再增加并行的 `payload_json` 或其他任务载体列。
- 知识库投影列 `document_id`、`stage_key`、`lane_key` 必须与 `body` 和共享信封对应字段相等；它们只为索引和调度查询服务。
- 持久信封禁止出现绝对路径、文件句柄、Python callable 或进程内状态。
- `source_revision` 是发布时的文件 MD5 或版本。文件已变化的旧任务必须在业务执行前失效。
- `input_hash` 由源版本、上游产物 hash、阶段执行器版本、schema 版本和适用的模型/prompt/preprocess 版本共同计算。只有 hash 相等的已有产物可以复用。

## 队列、租约和事件模型

统一队列表新增以下字段，既有终态历史保持不可变。

| 字段 | 含义 |
|---|---|
| `attempt` | 单调递增的实际执行次数。 |
| `lease_token` | 一次领取专属 UUID 栅栏令牌。 |
| `lease_owner` | Dispatcher 发放的执行单元身份。 |
| `lease_expires_at` | 领取失效时间。 |
| `heartbeat_at` | 执行单元最后一次心跳。 |
| `retry_at` | 重试最早可领取时间。 |
| `failure_class` | `source`、`validation`、`provider`、`resource`、`timeout` 或 `internal`。 |
| `resource_profile` | 从阶段注册表复制的不可变资源声明。 |
| `executor_pid` | 当前执行进程 PID，仅用于观测和进程退出确认，不作为任务权威。 |

队列状态保持简洁：

```text
pending -> running -> completed | failed | cancelled
              |\
              | -> pending（可重试失败或租约失效后，等待 retry_at）
```

`ready_status` 细分 `pending`：`ready`、`waiting_dependency`、`paused`、`scheduled`。前端状态由这些持久字段推导，不能从某个 worker 日志猜测。

必须满足以下不变量：

- `running` 任务必须有非空 lease token、owner、expiry 和 heartbeat。
- 完成、失败、取消和心跳更新都必须使用 `WHERE id = :task_id AND lease_token = :lease_token`。过期执行器不得覆盖新一次尝试。
- 对知识库任务建立 partial unique index：同一 `(task_type, document_id, stage_key)` 在 `pending` 或 `running` 时最多一行。
- 领取在一个事务内完成：用 `FOR UPDATE SKIP LOCKED` 选一条合格任务，更新为 `running` 并写入新租约，随后返回信封。
- 仅当租约缺失，或租约过期且心跳失效时才回收任务；回收必须记录原因并递增 `attempt`。
- 复用现有 `framework_event_log`，但必须改造 `backend/app/services/event_bus.py`：新增接受当前 `AsyncSession` 的“仅追加事件”接口和 `dedup_key` 唯一约束。当前 `emit_module_event()` 的独立 session + 同步 handler 调用不得用于阶段结算。产物写入、阶段运行结算、文档状态更新和 `stage_settled` 事件必须在同一事务提交；Dispatcher 在提交后异步消费事件。

Dispatcher 使用 PostgreSQL advisory lock 作为 leader 租约。只有 leader 可以计算配额或启动执行单元；任务运行期间不持有数据库事务。

## 执行进程暴毙处理

执行器不是无监管的子进程。Dispatcher 内的任务监督器持有 `task_id`、`lease_token`、`executor_pid` 和资源画像，并独立观察子进程。它不依赖业务 handler 的 event loop，因此 CPU 密集或原生库阻塞时仍能持续确认进程是否存在。

| 情况 | 判定 | 系统动作 |
|---|---|---|
| 进程正常运行 | PID 存在，监督器每 5 秒更新 `heartbeat_at` 并续租。 | 保持运行；长任务不会仅因耗时长被误回收。 |
| 进程正常结束 | 进程退出且结果事务用当前 lease token 成功提交。 | 标为完成、跳过或业务失败；随后退出监督。 |
| 进程突然退出 | PID 已消失，或监督器收到非零退出码。 | 立即停止续租，记录退出码；任务在短退避后以 `resource` 或 `internal` 失败重试。 |
| 进程卡死但仍存在 | 超过阶段 hard timeout，或连续缺少业务进度心跳。 | 先请求优雅退出；超过宽限期仍不退出则杀死进程，等待租约恢复。 |
| 整机重启/Dispatcher 暴毙 | 租约不再被续期，或历史遗留行缺少租约。 | 新 leader 只回收租约缺失或 `lease_expires_at` 已过期的任务。 |
| 旧进程晚到回写 | `lease_token` 已被新尝试替换。 | SQL `WHERE id AND lease_token` 更新 0 行，旧结果被拒绝；不会覆盖新结果。 |
| 已做完但提交数据库时断线 | 没有完整结果事务或 `stage_settled` 事件。 | 租约恢复后重试；阶段开头按 `input_hash` 检查，已成功写出的产物会被安全复用。 |

租约不是固定等到超时才检查：监督器每 5 秒续租一次；租约时长至少为 3 个心跳周期加上数据库缓冲。业务“进度心跳”与租约心跳分开记录：前者用于发现卡死，后者用于证明进程尚存。每个阶段还声明 hard timeout，超时的活进程也不能无限占着资源。

## 单任务资源账与计算

每一次尝试都要写一条 `framework_task_attempt_metrics` 资源账本行。它是观测历史表，不是队列，也不参与任务抢占。它至少记录：

```text
task_id, attempt, lease_token, stage/lane, executor_pid
开始/结束时间、退出码、CPU 秒数
开始/结束 RSS、峰值 RSS、主机可用内存
读取/写入字节数、临时文件大小
GPU 设备、开始/结束/峰值显存、观测来源和可信度
provider/model、等待额度时间、网络耗时、结果状态
```

资源账的计算分成两层，不能混在一起：

1. **单任务实际消耗**：监督器按 PID 定期采样。内存以本次 `peak_rss_mb` 为准，CPU 以进程 CPU 秒数的增量为准，GPU 以能取得的进程显存为准，磁盘 I/O 以进程读写字节增量为准。执行结束后形成不可变的一次尝试记录。
2. **整机还能承受多少**：Dispatcher 同时采样整机 CPU、可用内存、GPU/显存、磁盘压力、数据库连接余量和云端额度。它按任务类型过去成功尝试的 P95 峰值来估算下一条任务，而不是只看当前瞬时 CPU。

本地任务在某个资源池的可新增数按下式取最小值：

```text
可新增任务数 = min(
  该阶段硬上限 - 正在运行数,
  floor((可用内存 - 安全预留) / max(该阶段 P95 峰值 RSS, 最小估算值)),
  CPU 预算允许数,
  GPU/显存预算允许数,
  数据库/解析器允许数
)
```

云端 LLM/VLM 不使用上述 CPU 数量来扩容，而是取 `provider/model 并发额度`、`剩余限流额度`、`熔断状态` 和 `配置硬上限` 的最小值。GPU 指标不能可靠读取时，GPU 允许数只能使用保守配置值，并把可信度标为未知。

资源账会直接回答三个运维问题：哪一个 task type 最吃内存、某次高内存是否在进程退出后释放、以及现在还能安全启动多少同类任务。若进程退出后整机内存没有回落，问题被标记为宿主服务或外部模型服务泄漏，不能误归因到已退出任务。

## 工程化加固清单

以下项目不是锦上添花，而是本架构启用前必须具备的工程条件。

### 运行目标和可量化门槛

Dispatcher 不能只报“正在运行”，必须按部署配置记录并校验以下目标：

| 目标 | 必须度量的值 | 失败时动作 |
|---|---|---|
| 分配时延 | ready 任务从入库到领取的 P50/P95/P99，按 lane 和优先级拆分。 | P95 超过配置目标时告警，保留当轮拒绝原因。 |
| 恢复时延 | 执行进程消失到任务重新可领取的耗时。 | 超过“租约 + 一轮轮询”的目标时告警。 |
| 重复率 | 同一 `input_hash` 的真实重复执行次数。 | 非零即按栅栏、唯一约束或产物提交故障排查。 |
| 资源保护 | 内存/显存紧急水位触发后仍新领任务的次数。 | 必须为零；非零视为发布阻塞。 |
| 云端健康 | provider/model 限流、超时、熔断、等待额度时间。 | 只暂停受影响 provider/model，并给出恢复时间。 |

这些目标的阈值属于部署配置，不能写死在 Python 中。每一次调度决策、资源观察和告警都带 `config_version`，因此之后能回答“当时为什么会放出这条任务”。

### 配置、权限和人工控制

- 当前 `task_worker.json` 在重构后仍必须有 Pydantic schema、版本号、范围校验和安全默认值；加载失败时 Dispatcher 保持只读，不得以空配置无限领取任务。
- 资源画像、超时、重试和 provider 配额按 `TaskDefinition` 版本化。修改后只影响新领取任务，运行任务继续使用领取时冻结的画像。
- 暂停、恢复、drain、取消、提高配额都必须持久化操作人、原因、时间和可选到期时间；禁止只改内存变量或悄悄编辑配置文件。
- 执行器只能拿到已经授权的文件引用和最小任务信封；不得把用户 JSON 拼进 shell 命令、路径或 SQL。
- `framework_task_attempt_metrics` 按原始明细保留固定周期，之后按小时/天聚合；指标标签只允许有限集合的 task type、stage、lane、provider 和失败类别，禁止把文件名、用户输入或 document_id 当高基数指标标签。

### 数据库和发布门禁

- migration 必须先增加字段、索引和约束，再启用新入口；大表索引使用 PostgreSQL 合适的在线建索引方式，避免维护窗口内长时间锁表。
- 启用前 preflight 必须验证：全部已注册 task type 都有 `TaskDefinition`，所有活跃 `running` 行都有有效租约，所有旧 worker 已停止，所有未完成知识库任务可被新信封表示。
- 任务状态、事件日志、产物和阶段运行记录的事务边界必须有集成测试；禁止用“先 commit 任务结果、后发 Python 事件”的方式碰运气。
- `failed` 行就是终态失败库，不另建隐性死信队列。失败分类、最后错误、人工重试资格和下一步建议必须可查询。

### 测试、压测和故障演练

| 测试层 | 必须覆盖 |
|---|---|
| 纯单元测试 | 配额公式、资源预算、DAG 就绪判断、重试退避、输入 hash 和配置校验。 |
| 数据库并发测试 | 多个 Dispatcher 同时 claim、唯一约束、lease token 栅栏、过期租约回收、事务中断。 |
| 进程故障演练 | 在执行前、执行中、产物写入前、事务提交后分别 `SIGKILL`；验证不会丢任务或重复产物。 |
| 资源压力测试 | 用可清理的标记任务制造 CPU、RSS、I/O、GPU/云端限流压力，验证预算会收缩且能恢复。 |
| 回放压测 | 对脱敏的真实 backlog 快照回放分配决策，不调用真实模型；比较等待时延、公平性和资源峰值。 |
| 端到端验收 | 使用带测试标记且可清理的文件，从发布到后继 DAG、暂停、恢复、重启完整走一遍。 |

### 进程与时钟细节

- 监督器管理进程组，而不是只保存裸 PID；杀死任务时要清理子孙进程，避免解析器或转换器变成孤儿。
- PID 观测同时保存进程启动时间，避免操作系统复用 PID 后把新进程误认成旧任务。
- 时间判断只以数据库时间为权威；进程本地时钟仅用于耗时指标，不能决定租约是否过期。
- 所有外部调用都有连接、读取、总时长三类超时；取消后有有限宽限期，超过宽限期才强制终止。

### 初始数据不足时的保守策略

新架构刚上线时尚没有足够 P95 历史数据。此时每个资源画像必须提供保守的初始 RSS/VRAM 和并发上限；只有累计达到配置数量的成功样本后，才允许用观测 P95 替代初始值。任何失败、异常小样本或未知 GPU 数据都不得自动把并发放大。

## 阶段执行器契约

知识库阶段拆为独立 Python 文件，在同一注册表中声明，并实现统一接口：

```python
class StageExecutor(Protocol):
    async def is_satisfied(self, context: StageContext) -> ExistingResult | None: ...
    async def run(self, context: StageContext) -> StageOutput: ...
    async def commit(self, context: StageContext, output: StageOutput) -> StageResult: ...
```

执行顺序固定：

1. 验证租约，并通过 `file_id` 访问检查解析源文件。
2. 在读取或写入业务数据前拒绝已过期的 `source_revision`。
3. 按阶段和 `input_hash` 查询产物账本。
4. 命中有效产物时返回 `skipped/already_satisfied`；这是可见的完成结果，不能伪装成业务成功。
5. 只执行自己的阶段，不发布任何下游任务。
6. 原子提交阶段产物、`kb_pipeline_stage_runs`、文档阶段状态、指标和 `stage_settled` 事件。
7. 释放本地资源并退出执行单元。

Dispatcher 消费 `stage_settled`，从持久的阶段/产物事实判断 DAG，并通过统一发布器创建每一个新就绪后继节点。这包括前置汇合：只有 `profile` 和 `graph` 都得到匹配输入的有效产物后，才发布 `relations`。

知识库 DAG 只允许声明式定义。每个阶段注册记录执行器模块、前置节点、lane、资源画像、优先级类、执行器版本和硬并发上限。保留当前逻辑图：

```text
source_validate
  -> parse_index + raw_text + optional page_render
page_render -> raw_ocr + raw_vision
parse/raw prerequisites -> fusion
fusion -> profile + graph
profile -> cognitive_index
profile + graph -> relations
```

执行器不得修改 DAG 定义，也不得读取其他阶段的进程内存。

## Dispatcher 循环

Dispatcher 是持久轮询器，不是传统内存任务队列。

- 没有合格任务时，每 5 到 10 秒轮询一次。
- 存在合格 backlog 时，每 1 到 2 秒轮询一次。
- 发布、结算、重试到期、暂停变更和执行器退出均发送 PostgreSQL `NOTIFY`，立即唤醒下一轮；轮询始终保留为通知丢失后的兜底。
- 每轮用一个一致性快照读取按 `lane_key`、`stage_key`、优先级类和重试资格分组的 ready/running 数，以及资源/供应商观测。
- 每轮写入调度决策记录：输入、分配、领取和拒绝原因。因此任一分配都可由数据库复现。

Dispatcher 不扫描文件、不调用 LLM、不解析文档，也不会在等待执行器时占用数据库连接。

## 资源池与分配算法

线程不是一份共享总容量。以下资源池独立计算容量：

| 资源池 | 当前 lane | 主要约束 |
|---|---|---|
| 本地 CPU | `local_preprocess` | CPU、主机内存、磁盘/进程上限、解析器上限 |
| 本地派生 | `derived_index`、`relation_build` | DB 连接池、CPU、主机内存、阶段上限 |
| 视觉 | `vision_analysis` | 供应商额度或 GPU VRAM、主机内存、模型健康 |
| LLM | `llm_analysis` | 供应商/模型并发额度、限流、失败熔断状态 |

每个阶段声明资源画像：硬并发上限、预估 P95 RSS/VRAM 增量、超时以及适用的 provider/model。资源池预算等于配置硬上限和所有实时约束中的最小值。

本地任务要求其**所有**所需资源都有余量，不能采用“CPU、GPU、内存三者任意一个低于 80% 就继续加线程”的规则。该规则会在 CPU 空闲时把内存打满。连续 2 到 3 个采样窗口低于扩容水位才可逐次增加一个执行单元；达到 80% 警戒水位后停止新领取；主机内存或 VRAM 到紧急水位时立即停止领取。GPU 遥测未知时使用保守固定上限并记录 `confidence=unknown`；无可靠来源时系统不得声称 95% 准确率。

云端工作由 provider/model 并发、限流余量、熔断状态和近期错误率共同控制。本机 CPU 空闲不能提高云端并发。

同一资源池内使用按缺口的加权公平分配：

```text
活跃阶段：ready_count > 0
weight(stage) = ready_count + aging_boost
基础分配：槽位足够时，每个活跃阶段先得一个槽
剩余分配：按 weight(stage) 比例分配
deficit(stage) = target_allocation - running_count
下一个领取：选择最大正 deficit 的合格阶段
```

同分时按优先级类、再按最早可领取任务决定。没有 ready 任务的阶段不保留槽位。因此 A=100、B=50、C=0、D=20 时，每个活跃阶段先获得地板槽位，其余槽位约按 `100:50:20` 分配，既不会饿死小阶段，也不会被固定 worker 列表绑死。

## 内存与进程退休

每次执行结果记录开始 RSS、可获取时的峰值 RSS、结束 RSS、时长和资源观测可信度。Dispatcher 通过滚动 P95 增量限制后续本地领取。执行器每任务退出，普通原生库和解析器内存由 OS 回收。

执行器超过单任务 RSS/VRAM 上限时会被终止，租约交给恢复机制处理，失败分类为 `resource`。重复资源失败触发阶段级熔断，只暂停该阶段，不得无限创建替代进程。

## 一次切换纪律

本架构作为一个完整替换上线，不存在两个竞争调度模式并存。

1. 进入维护 drain：停止旧 watchdog 创建或扩容 worker，停止旧式领取，等待有效租约结算或到期。
2. 对账队列行、pipeline run、stage run 和文档锁，将它们收口为终态、可重试态或明确暂停态。不得存在无有效租约的 `running` 行。
3. 一起部署框架队列/租约/事件日志 schema、Dispatcher、通用执行器入口、资源观测器、所有已注册 task type 的适配器，以及知识库执行器/DAG 代码。
4. 将仍有效的未完成任务按新固定契约重新发布。知识库命中已有匹配产物的任务结算为 `already_satisfied`，不得重复计算。
5. 原子启用 Dispatcher Leader 及其 watchdog 入口，然后永久禁用旧的 self-claim worker loop 和独立的 `kb_pipeline_autofill` 控制循环。以后 reconciliation 只归 Dispatcher。

启用 Dispatcher 前可按正常部署回滚。新 Dispatcher 已领取任务后，回滚属于维护操作：先 drain 租约、保留持久产物与结果，绝不让已退休控制面重新领取新体系已领取的行。

## 运行视图与告警

任务面板和 toolkit snapshot 必须展示：

- 各阶段/lane 的 ready、等待依赖、暂停、定时、运行、重试、完成、跳过、降级、失败和取消数量；
- 活跃租约年龄、心跳年龄、回收次数和栅栏失败；
- 资源采样来源和可信度、配置上限、计算预算、运行数和分配缺口；
- provider/model 额度、limiter 等待、限流/熔断状态和实际时延；
- 执行器 RSS/VRAM 分布、强制退休和未释放资源诊断；
- 产物缓存命中（`already_satisfied`）和源版本过期拒绝数量；
- 每条 ready 任务未被领取的准确原因。

租约过期、任务行与知识库 pipeline-run 状态不一致、文档锁陈旧、资源遥测缺失、连接池耗尽、或存在 backlog 的阶段被配置/熔断暂停时，必须告警。

## 验收标准

没有满足全部项目，就不允许启用 Dispatcher 领取真实队列。

| 验收项 | 通过标准 | 验证方式 |
|---|---|---|
| 发布入口完整性 | runtime 已注册的每一个 task type 都有 `TaskDefinition`；所有新任务的 `parameters` 均通过固定信封校验；没有业务代码直接创建可执行 `SystemTaskQueue`。 | 注册表与 `_HANDLERS` 集合比较测试；静态扫描；任务提交接口和知识库 ingest/retry/backfill 集成测试。 |
| 单一领取者 | 同一时刻只能有一个 Dispatcher Leader；watchdog 最多拉起一个 `task_worker_main` Dispatcher；旧 `_worker_lane_loop` 不参与领取。 | PostgreSQL advisory lock 并发测试；watchdog 进程测试；运行状态探针。 |
| 原子领取与栅栏 | 多个并发领取请求对同一行只能成功一次；每个 running 行都有有效 lease；旧 token 完成写入必须更新 0 行。 | 数据库并发测试不少于 100 次竞争领取；过期 token 回写测试。 |
| 进程暴毙恢复 | 在执行前、执行中、产物事务前、提交后分别强制结束执行进程，任务不会丢失；已经持久化的产物不会重复写入。 | `SIGKILL` 故障演练和 lease recovery 集成测试；每种位置至少一次。 |
| 稳定复用 | 同一 document/stage/source revision/input hash 重复发布只保留一条活跃任务；已有效完成时结果为 `skipped/already_satisfied`。task/run ID 变化不得改变稳定 hash。 | 知识库阶段语义测试和真实小样本端到端测试。 |
| DAG 正确性 | `source_validate` 后的分叉、视觉前置、fusion 后的 profile/graph，以及 profile+graph 到 relations 的汇合均只按持久事实发布一次；重启后可继续。 | `test_pipeline_stage_semantics.py` 扩展为 DAG/restart/重复事件测试。 |
| 事件事务 | 阶段产物、stage run、文档状态和 `stage_settled` 事件要么全部提交，要么全部没有；当前 event bus 的独立 session 路径不得用于此结算。 | 数据库事务中断测试；`test_event_bus_retry.py` 增加同事务 append 和 dedup 测试。 |
| 资源保护 | 每个 attempt 都写 CPU/RSS/I/O 和可用时的 GPU 指标；高内存或高显存时新本地领取数变为 0；GPU 不可观测时走保守上限。 | 合成资源压力任务；attempt metrics 查询；Dispatcher 决策回放。 |
| 云端隔离 | provider/model 429、超时或熔断只影响对应模型任务，不阻塞 local_preprocess、derived 或 relation lane。 | 模拟 provider 限流；检查 `retry_at`、paused 原因和其他 lane 继续推进。 |
| 当前队列状态收口 | 切换前所有旧 `running` 队列行、知识库 pipeline run、stage run 和文档锁都被对账为有效租约、终态、可重试或明确 paused；不存在无主 running。 | 现有 audit/reconcile 能力加新 lease 对账，输出零个未分类 orphan。 |
| 现有业务不回退 | 知识库 ingest、状态查询、搜索可用性、阶段跳过、失败治理和现有公开 capability 继续满足当前 sandbox 与模块契约。 | `modules/knowledge/sandbox/test_module.py`、模块后端测试、capability contract diff、目标 API probe。 |
| 可观察性 | 页面和 toolkit 同时展示 ready、waiting、paused、running、retrying、skipped、degraded、failed 及每个拒绝领取原因；当前 3531 条 paused backlog 必须显示为 paused。 | dashboard/API 断言和 live `knowledge_pipeline_snapshot` 检查。 |
| 切换完成 | `task_worker.json` 不再含 worker 进程槽/多 lane 自抢语义；`pipeline_autofill_service.py` 不再注册队列任务；旧 worker 扩容路径不可执行。 | 配置 schema 测试、注册表测试、watchdog 启动测试和进程清单检查。 |

## 实现归属

实现是一次完整架构变更，有两个仓库归属区，但它们共同评审、共同启用：

- 框架部分：`backend/app`、`backend/tests`、framework migration、任务 worker/dispatcher 入口和底层开发文档。
- 模块适配部分：每个当前已注册 task type 的模块提供 `TaskDefinition` 适配；知识库额外实现 `modules/knowledge/backend`、`modules/knowledge/sandbox` 中的 DAG、模型、服务和测试。只有公开行为变化时才调整 manifest 契约和模块 README。

两块目录边界不是分阶段设计。只完成其中一块的变更仍属未完成，禁止启用。

## 基于当前代码的改造落点

下表只列当前已存在的文件及其必须承担的改造；除知识库阶段文件外，不预先虚构新服务目录或第二套入口。确有拆分需要时，拆出的文件仍归这些现有模块所有，并必须有对应测试。

| 当前文件 | 当前职责 | 目标改造 |
|---|---|---|
| `backend/app/services/task_worker.py` | 注册 handler、多 lane 自抢、静态公平计算、完成/重试和 worker RSS 退休。 | 原地重构为唯一 Dispatcher：保留注册表但升级为 `TaskDefinition`；删除 `_worker_lane_loop` 的自领取模型；在此文件内完成统一发布、一次分配、lease/heartbeat/fencing、子进程监督和结果结算。 |
| `backend/app/task_worker_main.py` | 作为独立 worker 进程入口，启动 `start_worker()`。 | 保留该入口和启动脚本兼容性，但启动的是一个 Dispatcher Leader，不再启动多 lane worker。 |
| `scripts/backend_watchdog.sh` | 按 pending 数量拉起多个 `app.task_worker_main` 进程。 | 改为同一时刻最多一个 Dispatcher 进程；任务并发由 Dispatcher 依据资源预算创建单任务执行进程，watchdog 不再按 backlog 增加抢任务进程。 |
| `backend/app/main.py`、`backend/app/services/system_status_service.py` | web 进程可 autostart worker，健康接口按旧 worker 语义判断。 | 保留 `TASK_WORKER_AUTOSTART` 开关，但改为 Dispatcher 启动语义；健康状态必须报告 leader、可执行 backlog、活跃租约和资源观测，而不是 lane 数。 |
| `backend/app/models/system.py` | 任务表模型和 `ensure_framework_scheduling_columns()` 运行时 schema guard。 | 在同一 schema guard 中新增 lease、heartbeat、attempt、PID、retry 和资源画像字段、唯一活跃任务索引，以及 `framework_task_attempt_metrics` 观测表；保留现有队列 ID、历史任务和 DAG 投影列。 |
| `backend/app/routers/tasks.py` | 管理端直接按 `module/task_type/parameters` 插入任务、直接重试/取消。 | 所有写入改走 worker 内的统一发布接口；重试和取消必须检查 lease；任务详情返回 ready/paused/running/retry/terminal 与 lease 信息。 |
| `backend/app/services/event_bus.py` | 独立 session 持久事件并同步投递，失败后重放。 | 新增同事务 append 和 `dedup_key`；保留既有普通事件行为。阶段结算只 append，后继发布由 Dispatcher 消费，不在 handler 内同步调用。 |
| `backend/data/config/task_worker.json` | 20 进程/10 lane、静态 stage/lane 并发、暂停和动态权重配置。 | 保持此实际配置文件路径，删除 process-slot/lane 自抢语义；改为资源水位、每 task type/stage 资源画像、provider/model 配额、超时、重试、暂停及安全初始上限。 |
| `modules/knowledge/backend/services/document_service.py` | `enqueue_pipeline_task()` 直接创建 `kb_pipeline_stage` 根行。 | 改为调用统一发布接口；仍以 `document_id` advisory lock 和活跃唯一约束防止重复根任务。 |
| `modules/knowledge/backend/services/pipeline_service.py` | `_run_stage()` 执行所有阶段，`_pipeline_stage_handler()` 同时执行、记账并 `_enqueue_successors()`。 | 保留 DAG 常量、阶段就绪判断、stage run 与 artifact 账本；将每个阶段业务体拆到同模块的独立阶段文件；handler 不再直接 enqueue successor，而是向 Dispatcher 返回稳定的阶段结果和后继就绪事实。稳定缓存 hash 必须去除 `task_id`、`pipeline_run_id`。 |
| `modules/knowledge/backend/services/pipeline_autofill_service.py` | 每小时注册并执行 `kb_pipeline_autofill` 队列任务。 | 删除其 task handler 注册和 recurrence 创建；保留“寻找未完成/可重试文档”的查询，改为 Dispatcher 的统一 reconciliation 周期调用。 |
| `modules/knowledge/backend/services/model_routing.py` | 每个 worker 进程内限制模型调用，并可写暂停配置。 | 进程内 limiter 仅保留为单任务保护；全局 provider/model 配额移到 Dispatcher 持久决策中。自动暂停必须写明原因、影响范围和恢复条件。 |
| `modules/knowledge/backend/services/dashboard_service.py`、`modules/knowledge/backend/router.py` | 从 `task_worker.json` 和队列行拼装知识库进度。 | 读取 Dispatcher 的持久状态与 attempt metrics；保持当前 API/能力名称，新增状态字段时显式映射，不把 paused 误报为 queued。 |
| 当前 handler 注册点：`modules/scheduler/backend/router.py`、`modules/memory/backend/router.py`、`modules/agent/backend/bootstrap.py`、知识库的 `chunk_embedding_service.py`、`enterprise_import_service.py`、`pipeline_service.py`、`pipeline_autofill_service.py` | 向旧 worker 注册 task handler。 | 每一个已注册 task type 必须同时提供 `TaskDefinition`。非知识库 handler 先作为无 DAG 的单节点任务适配，不重写其业务实现；未适配者在切换前阻止发布。 |
| `backend/tests/test_task_worker_semantics.py`、`backend/tests/test_task_worker_recovery.py`、`backend/tests/test_event_bus_retry.py`、`modules/knowledge/backend/tests/test_pipeline_stage_semantics.py`、`modules/knowledge/sandbox/test_module.py` | 现有 worker、事件和知识库阶段语义测试。 | 替换或扩展为本方案的 lease、并发领取、进程退出、事务事件、稳定 hash、DAG、资源预算和端到端可清理样本验收。 |

关键边界：Framework Dispatcher 不导入 Knowledge 内部代码。知识库通过注册的 `TaskDefinition` 提供“执行某阶段”“检查是否已有稳定产物”“根据持久阶段事实计算后继”的回调；Dispatcher 只负责何时调用、能否分配和如何持久化。这样仍然是一套框架调度器，不会形成 framework 直接依赖模块的反向耦合。

## 预判运行情况

| 发生的情况 | 系统实际动作 | 页面/日志应该看到什么 |
|---|---|---|
| 用户上传一份新 PDF | 发布器只写一条 `source_validate`；分配器在本地资源允许时启动一个执行进程。 | 文档显示“排队中”再变“处理中”，而不是一上传就假装完成。 |
| 用户连续点两次“分析” | 发布器命中活跃唯一约束，返回已存在任务。 | 显示同一个任务号和“已在处理中”，不产生两条相同任务。 |
| 当前已有同版本产物 | 节点开头查到匹配 `input_hash`，写 `already_satisfied`，不调模型。 | 显示“已复用已有结果”，耗时接近零。 |
| A 节点 100 条、B 节点 50 条、C 节点 0 条、D 节点 20 条 | 分配器先给 A、B、D 最小槽位，再把剩余槽位主要给 A、其次 B、最后 D。 | 面板能看到每个节点的 backlog、运行数、目标槽位和缺口。 |
| CPU 空闲但内存已高 | 本地任务不再扩容；内存到紧急水位时停止新领取。 | 显示“等待本地内存”，不会无限开进程。 |
| GPU 无法可靠读数 | 使用保守 GPU 并发上限，不以猜测的数值扩容。 | 显示“GPU 观测未知，采用保守上限”。 |
| 云端 LLM/VLM 返回 429、超时或熔断 | 该 provider/model 暂停新任务，任务按 `retry_at` 延后；其他本地 lane 继续运行。 | 显示“等待云端额度/重试时间”，不把它误报成机器卡死。 |
| 一个解析器或原生库撑爆内存 | 该执行进程被终止，租约过期后回收；重复发生则只熔断这个阶段。 | 看到 `resource` 失败、峰值内存和该阶段暂停原因。 |
| 执行进程崩溃或电脑重启 | 没有新心跳，租约到期后由分配器重新排队；旧进程即使复活也不能用旧 token 写回。 | 原任务显示“恢复中/第 N 次尝试”，不会出现两份产物。 |
| 文件被删、权限变化或内容已变 | `source_validate` 拒绝旧版本任务，不读取物理路径。 | 显示“源文件不可用/版本已变化”，而不是反复解析错误文件。 |
| 阶段已经成功但写下游前进程断了 | 当前阶段结果和 `stage_settled` 事件同事务已落库；分配器重启后补发后继。 | 当前阶段完成，下游稍后自动进入排队，不会卡成孤儿任务。 |
| 全部任务做完 | 执行进程都退出，分配器退回 5 到 10 秒空闲轮询。 | 没有常驻的 20 个空 worker，面板显示空闲。 |
