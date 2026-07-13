# Agent 对话执行编排重构方案

## 先看图

```text
[用户请求 + 已授权文件/任务上下文]
                  |
                  v
[SQL 权限裁剪层]
  用户有效权限 + 组织范围 + 对象访问
  -> 只返回已授权 capability / 经验 / 数据引用
                  |
                  v
[运行时能力注册表]
  与 SQL 授权结果求交集 -> 本回合能力快照(hash) -> 混合检索 Top-K
                  |
                  v
[分层成功经验]
  全局通用路径 + 部门/岗位经验 + 个人偏好
                  |
                  v
[LLM 结构化规划]
  只输出：动作、参数、依赖、完成条件、需要确认项
                  |
                  v
[通用校验器]
  快照存在？实时权限仍有效？参数/schema/审批/资源/幂等性允许？
                  |
                  v
[通用动作图执行器]
  领取动作 -> call_capability -> SQL/对象权限结果投影 -> ResourceRef
                  |
        +---------+----------+
        |                    |
        v                    v
[目标已满足]          [信息不足/可恢复错误]
  返回 SSE/结果          将观察结果交给 LLM 重新规划
        |                    |
        +---------+----------+
                  |
                  v
[持久化]
 checkpoint + 工具账本 + 工作流账本 + 可观测性
                  |
                  v
        [服务重启后读取 checkpoint，继续未完成动作]
```

一句话：模型决定“为了完成用户目标，要组合哪些已经注册的能力”；代码只负责证明这件事可执行、安全、可恢复，并把真实结果交回给模型和用户。

## 目标、范围与完成定义

本次是一次性替换 Agent 对话工具执行主链路的架构任务，不是给现有循环再加一层补丁。完成后 Agent 不再依赖“先列工具、再读工具、再猜参数”的默认方式，也不再依赖按图片、文件、知识库等业务名称写死流程模板。

目标：

1. 每次对话都从**框架运行时 capability registry**取得按用户有效权限 ID 过滤后的真实能力快照；Agent 不维护第二份工具真相。
2. 模型基于检索出的能力契约，输出可验证、可持久化的动作图（ActionPlan/DAG），而不是直接任意调用工具或依赖固定业务计划。
3. 执行器只包含通用机制：schema、引用绑定、权限、审批、资源、超时、幂等、重试、检查点和结果交付；不存在 `if 图片 -> 某工具`、`if 知识库 -> 某流程` 一类业务路由。
4. Agent 服务重启、SSE 断连或单个执行进程异常时，已完成动作不重复产生副作用，未完成动作可从数据库继续或请求重新规划。
5. 旧的默认元工具循环、workflow recipe 文本注入和重复提示词路径被删除，仓库与数据库只保留一条实际执行主链路。

范围是一次跨边界改造：`modules/agent/` 是编排与账本的归属；`backend/app/services/module_registry.py` 需要增加通用 capability 执行元数据，作为框架接口变更一并完成。用户已明确要求本次重构方案覆盖真实项目整体，因此该框架改动与 Agent 改动必须同一个变更集交付，不能在 Agent 内另造隐藏注册表。

不在本次新增：第二个 Agent loop、第三方 Agent 框架依赖、旁路队列、物理绝对路径传递、按模块私有服务直接调用，或独立的云端线程调度器。知识库的持久任务仍由现有 `app.task_worker_main` Dispatcher 负责；Agent 对异步能力只处理已有的任务/制品引用。

## 当前系统事实与冲突判定

本方案以当前代码为准，不假设不存在的组件。

| 当前节点 | 当前事实 | 与目标的关系 |
|---|---|---|
| `conversation_runtime.py` | 新会话和 checkpoint 续跑都会调用 `tool_discovery.build_tools(user.role)`，再进入 `ToolLoopRuntime` | 保留对话入口与 SSE；把“生成工具列表”替换为“生成能力快照和目录检索结果” |
| `tool_discovery.py` | 默认只暴露 `skill_list`、`skill_describe`、`skill_use` 三个元工具 | 是当前 80.6% 元工具占比的直接根因，必须替换默认策略 |
| `tool_loop_runtime.py` | 已有模型调用、工具调用、SSE、超时、checkpoint 写入和错误处理 | 保留为唯一执行循环，内部改为通用 ActionPlan executor，不再保留第二条旧循环 |
| `checkpointer.py` / `agent_checkpoints` | 已能持久化 `messages`、`tool_events`、`timeline` 等续跑状态 | 扩展为持久化快照、计划、动作状态与 ResourceRef，避免另建内存状态 |
| `intent_preflight.py` | 当前规则分类中包含 `document_analysis`、`internal_knowledge` 等业务倾向和 `first_actions` 提示 | 保留通用的风险/预算/澄清判断；删除业务动作建议和工具名提示 |
| `context_injectors/workflow_recipe.py` | 用字符 n-gram 匹配 `agent_workflow_recipes`，把历史 `steps/tools_used` 文本塞入系统提示词 | 这是第二套隐性流程编排，必须从主链路移除 |
| `workflow_recipe_service.py` 与 post-turn mining | 会挖掘“最短工具链”并持续注入下一轮 | 删除 recipe 注入、挖掘任务、模型和表；历史成功经验改由已有 trajectory/experience 检索提供证据，不拥有执行权 |
| `tool_discovery.py` 的 `content__write_ir` 分支 | Agent 层识别单一 capability，并执行专用 validate/correct/write 流程 | 验证/修复下沉为该 capability 的 contract 或 content 模块内部职责；Agent 不识别工具名 |
| `tool_loop_runtime.py` | 对 `skill_use` 的参数解包与快慢工具策略仍有特判 | 新执行器直接消费已验证的 capability action，不再把桥接工具视为特殊执行协议 |
| `RuntimeTaskSink.generate_completion_evidence` | 当前按工具名关键词猜测读写、制品和完成证据 | 改读 `output_schema` 与 `ResourceRef`，不再依赖工具名前缀 |
| `call_capability()` | 框架已是跨模块能力的唯一真实执行入口 | 保持为唯一调用入口，不让 Agent import 其他模块私有服务 |
| `agent_tool_calls`、workflow ledger、SSE timeline | 已有工具和工作流审计面 | 扩展字段/载荷并统一写入，不另建一套平行审计 |

因此，本方案不是和当前系统打架，也不是两套轮子：它复用当前入口、能力调用、检查点、账本与 SSE；删除的是“默认元工具发现”和“recipe 文本指挥执行”这两条重复决策路径。

当前权限覆盖并不缺失，但模型过粗：208 个 manifest public actions 全部写了 `min_role`，其中 `viewer` 111 个、`editor` 54 个、`admin` 43 个，约 46.6% 的能力被角色文本限制。框架 `require_permission()` 和 `call_capability()` 实际都按 `admin > editor > viewer` 比较；`framework_role_matrices.permissions` 只有少量系统管理布尔项，没有参与 capability 授权。现有用户表也只有单个 `role` 文本字段，没有部门、岗位或权限 ID 集合。因此“绝大多数工具通用、少数能力受限”是本次要迁移到的目标，不是当前事实。

当前真实诊断基线来自 `agent_runtime_snapshot(owner_id=4, days=30)`：18 条轨迹、3 条错误轨迹、58 次 `skill_list/skill_describe/skill_use`、14 次实际能力调用，元工具占比 80.6%。已观察到的失败包括：`knowledge__search` 被通用 18 秒超时截断 5 次、文件 ID 契约错误 2 次、JPG 被送入文本读取器、同一回合能力发现与实际调用不一致，以及编辑权限在执行之后才被拒绝。它们是本设计的回归样本，不是虚构的演示场景。

## 最终架构：LLM 规划，通用代码执行

### 1. 唯一能力真相与每回合快照

框架 `register_capability(...)` 的运行时注册仍是权威。扩展每个 capability 的通用 `execution_contract`，并让 manifest 的 `public_actions` 只承担发现元数据、由 `docs_audit`/契约校验防漂移。

```text
CapabilityExecutionContract
  input_schema / output_schema
  execution_mode: sync | async
  resource_class: fast | local_cpu | local_gpu | cloud_llm | cloud_vlm | long
  timeout_policy / retry_policy
  idempotency: required | supported | none
  side_effect_level / approval_policy
  trust_level: framework_verified | module_verified | external_untrusted
  output_reference_types: file | artifact | task | url | record
```

这里没有图片、知识库、PPT 等业务字段。模块在注册自己的真实 capability 时声明这份通用契约；Agent 只读取它。每次请求从 registry 按权限 ID、对象访问、暂停/健康状态过滤后，以规范化 JSON 算出 `catalog_hash`，并保存该快照的工具名、schema 摘要和 contract 摘要到当前 checkpoint。

Agent 可以维护一个按 `catalog_hash` 失效的**派生检索索引**（词法索引加已有 embedding 服务的语义向量）。它只能从 live snapshot 重建，不能单独注册能力或覆盖权限；hash 不同即废弃。这是缓存，不是第二个 capability registry。

### 2. 权限模型：默认通用，少数能力限制

权限不能继续使用 `min_role="admin/editor/viewer"` 作为 capability 的最终判断，更不能交给 LLM 判断。目标模型采用数值 ID，角色名称只保留为显示和管理分组，不参与执行时大小比较。

```text
[用户]
  direct permission IDs
  + permission-set IDs（一次授予一组）
  + 未来可选的部门/岗位 permission-set IDs
                  |
                  v
[PermissionResolver]
  解析为 effective_permission_ids = [1, 3, 5, 6, 7, 8]
                  |
                  v
[Capability Policy]
  required_permission_ids = []       -> 已登录用户默认可用
  required_permission_ids = [7]      -> 必须具备 7
  required_permission_ids = [7, 8]   -> 按 all/any 策略判断
```

数据库使用规范化关系表，API 和 Agent snapshot 使用用户易理解的整数数组：

| 数据 | 设计 |
|---|---|
| 权限目录 | `framework_permissions(id, stable_key, display_name, scope, enabled)`；ID 一经发布不可复用 |
| 权限组 | `framework_permission_sets` + set/permission 关系，一次给用户分配整组权限 |
| 用户授权 | user/permission 与 user/permission-set 关系；解析后返回 `permission_ids: list[int]` |
| capability 限制 | framework capability identity 与 permission ID 关系，另有 `match_mode=all/any` |
| 超级管理 | 使用受审计的系统权限组，不在代码中对文本 `admin` 永久放行 |

运行时 capability registry 仍是“能力是否存在、handler 是谁”的唯一权威；权限表只回答“谁能调用”，不能凭数据库记录创造一个不存在的 capability，因此不会形成第二套工具注册表。

权限裁剪是确定性的服务端安全边界，执行顺序固定为：

```text
数据库解析 PrincipalContext 和 effective_permission_ids
  -> SQL 查询当前用户允许的 capability identities
  -> 与 live runtime registry 求交集
  -> SQL 查询当前用户可见的经验/记忆/资源
  -> 生成已裁剪 catalog snapshot
  -> 只有这个 snapshot 可以进入 LLM
```

禁止先全量查询再让 Python、提示词或 LLM 判断是否可见。SQL 查询必须在 `WHERE/JOIN/EXISTS` 中同时约束 `user_id`、组织/部门/岗位 scope、permission IDs 和资源所有权；未授权 capability 的名称、描述、schema、历史经验和数据摘要都不能进入模型上下文。模型看到的不是“有这个工具但你不能用”，而是该工具根本不在候选集合中；只有用户明确请求受限操作时，服务端可以返回不泄露内部细节的结构化 `permission_denied`。

三道强制闸门：

1. **检索前**：SQL 只返回当前 principal 可见的 capability identity、ExperiencePattern、memory 和 ResourceRef。
2. **执行前**：`call_capability()` 使用数据库最新权限再次校验，不能只相信规划期 snapshot；权限已撤销则拒绝执行并使 plan 失效。
3. **结果入模前**：资源模块按 owner/share/ACL 再投影结果，只把授权字段和 ResourceRef 交给 Agent；原始数据库行、物理路径和未授权内容不能进入 observation。

catalog/experience 缓存键必须包含 `user_id + permission_version + organization_scope_version + catalog_hash`。用户权限、部门归属、共享状态或 capability policy 变化时，旧缓存与 checkpoint snapshot 立即失效；续跑必须重新执行 SQL 裁剪，不能复用旧权限结果。对 Agent 个人记忆、经验和轨迹表增加统一的 owner/scope 查询守卫，并为高敏感表启用 PostgreSQL RLS 作为纵深防御，避免某个新查询漏写过滤条件。

迁移时把现有角色能力映射为权限组，完成同一发布切换后删除 capability `min_role` 比较和前端 `roleLevels`。随后逐项复核 97 个非 viewer action：普通读取、搜索、生成等默认不要求额外 permission ID；系统配置、用户管理、删除、对外发送、高风险终端写入等才绑定原子权限。文件所有权、会话成员、artifact owner 等对象级校验始终保留，它们不是“工具权限”，不能因为 required IDs 为空而绕过。

### 3. 用户、部门与岗位上下文预留

组织架构不应默认参与授权权重，也不应把不同用户的私人记忆混在一起。本次先定义框架级 `PrincipalContext`，Agent、memory 和 capability snapshot 都只消费这一个接口：

```text
PrincipalContext
  user_id: int
  permission_ids: list[int]
  organization_id: int | null
  department_ids: list[int]
  position_ids: list[int]
  profile_version: int
```

当前没有组织数据时，后三项为 `null/[]`，所有个人记忆仍严格按 `owner_id=user_id` 隔离。以后增加组织架构时，由框架实现 organization/department/position 解析，Agent 不改主流程；部门记忆和岗位记忆使用明确的 `subject_type + subject_id` 作用域单独检索，并标注来源，不能覆盖用户私人记忆。

未来若公司决定让部门或岗位授予权限，只需在 `PermissionResolver` 增加一种 permission-set 来源；默认关闭，且与“部门/岗位用于记忆和个性化”是两个独立开关。这样不会因为某人属于销售部，系统就暗中给工具加权或越权。

### 4. 成功经验的共享边界与晋升

成功经验不能全部全局共享，也不能让每个用户从零探索。必须把“怎么完成一类目标的通用路径”和“这个用户喜欢怎么做”分开保存：

| 经验层级 | 保存内容 | 是否共享 | 示例 |
|---|---|---|---|
| 全局 | 已验证、已脱敏、跨部门仍成立的 capability 组合与完成条件 | 所有有权限用户 | 查找文件 -> 读取授权内容 -> 生成结果 -> 返回 ResourceRef |
| 组织/部门 | 只在该组织或部门成立的流程规则、常用能力组合 | 同组织/部门 | 销售材料需要经过部门知识检索与品牌检查 |
| 岗位 | 与岗位职责相关，但不依赖某个具体人的执行习惯 | 同岗位 | 设计岗位优先返回可编辑制品和预览图 |
| 个人 | 用户偏好、常用参数、输出位置、表达方式和本人验证过的变体 | 仅该用户 | 默认使用某种风格、输出到本人目录 |
| 会话 | 当前任务临时约束和已经完成的动作 | 仅当前会话 | “本次不要发布，只预览” |

SQL 先取当前用户可见范围的并集：`global + organization + departments + positions + user + conversation`，并排除当前权限不允许或引用对象不可见的经验；召回算法只能对这份已裁剪结果评分。层级不是简单覆盖关系，最终按以下因素统一评分：目标语义相关度、当前 capability contract/hash 兼容度、真实成功率、不同用户成功覆盖数、时效性和当前作用域贴合度。个人经验只在相关度相近时加分，不能因为“属于本人”就压过更可靠的全局路径。

经验只以结构化、去具体资源的形式保存：

```text
ExperiencePattern
  scope_type / scope_id
  goal_signature / preconditions
  action_pattern（capability identity + dependency，不保存具体 file_id）
  completion_evidence
  capability_contract_hashes
  success_count / distinct_user_count / failure_count
  confidence / last_verified_at / status
```

它是 Planner 的证据，不是可直接执行的脚本。LLM 仍需结合本轮 Top-K capability、用户对象和完成条件生成新的 ActionPlan；validator 再检查权限、schema、对象访问与 snapshot hash。旧经验引用的能力已撤销、schema 改变、权限不足或前置条件不成立时，直接降权/失效并重新规划，不能照搬旧路径。

经验沉淀采用逐级晋升：

1. 单次成功先记录为用户候选，只保存脱敏 action pattern 与完成证据。
2. 同一用户重复成功后成为个人已验证经验；参数偏好仍单独放在个人记忆，不混入通用路径。
3. 同部门多个不同用户在相同前置条件下成功，且不存在敏感参数，才可晋升为部门候选。
4. 跨部门、跨用户稳定成功并通过权限/隐私/回归验证后，才可发布为全局经验。
5. 失败、用户纠正或 contract 变化会降低 confidence；连续失效的经验自动停用，但历史审计保留。

全局和部门晋升不能把原始对话、文件名、file ID、客户数据或个人偏好复制给其他用户。自动晋升只生成候选，正式发布需满足可配置的样本数与成功率门槛；涉及写入、对外发送或删除的高风险路径还需要管理员审核。

现有 `agent_trajectory_records` 是原始事实来源，已有 experience matching 可作为检索入口；旧 `agent_workflow_recipes` 的文本步骤注入仍然删除。新的 experience index 是 trajectory 的脱敏派生投影，以 `scope + contract_hash` 失效，不是第二个执行器或固定工作流表。

### 5. 自动能力检索，而不是业务模板或默认元工具

目录检索输入为用户请求、最近上下文、已授权对象引用和未满足完成条件。候选集合必须来自 SQL 权限裁剪结果，检索器无权恢复被过滤的数据；随后再以混合算法并行召回：中文 embedding 语义分、名称/别名/参数的词法分、输入输出 `ResourceRef` 兼容分，以及当前用户可见的分层成功经验分；最后用 RRF/归一化分数融合。历史成功只改善召回和规划，不得绕过权限或把旧工具链变成模板。

每个 capability 的检索文档由模块契约提供紧凑字段：`brief`、`aliases`、`when_to_use`、`when_not_to_use`、关键参数、输入/输出 reference type。Agent 不维护按图片、知识库等划分的静态技能组。目录可按契约元数据动态分组用于展示，但分组没有路由权。

默认召回 Top-8（按上下文预算可在 5 至 12 之间调整），一次性把这些候选的完整 function schema 和简短使用边界交给规划 LLM，在同一次模型调用中选工具并生成 ActionPlan。不能把 208 个完整 schema 全量注入：它会显著增加上下文并让相似工具互相干扰；也不能让模型每轮先执行 `skill_list/skill_describe`。只有 Top-K 置信度不足或 validator 报告能力缺失时，才启用一次 `capability_search/describe` fallback。

模型默认只看到这些直接能力契约和计划 JSON schema，因此可以直接提出一个或多个动作。桥接能力本身不能越过快照调用真实能力。

这借鉴 Hermes 的正确部分：核心安全能力始终可见、目录按本次真实工具集重建、桥接调用沿用同一守卫与审计、用户与轨迹展示真实底层能力。也避免其不适合直接照搬的部分：不采用会话内存中的工具目录，不把搜索桥接当作每回合起点。

### 6. LLM 只输出结构化动作图

规划器使用 provider 的 JSON schema/structured output，输出通用对象，而不是 Python 分支或自然语言步骤：

```json
{
  "goal": "用户可验证的完成描述",
  "actions": [
    {
      "id": "a1",
      "capability": "module__action",
      "arguments": {"...": "..."},
      "depends_on": [],
      "expected_references": ["file", "artifact", "task"],
      "completion_check": "本动作成功的可验证条件",
      "approval_reason": ""
    }
  ],
  "final_completion_check": "最终目标如何判断完成",
  "need_user_input": []
}
```

动作参数可引用前序输出，例如 `${a1.references[0].id}`。引用绑定由 schema 和 reference type 验证，不能用字段名猜测或字符串替换。一个简单请求仍可得到只有一个动作的计划；复杂请求可得到 DAG。模型可以重规划，但触发条件仅是缺失输入、可恢复错误、快照变化或最终完成条件未满足，且受最大规划轮数/预算约束。

### 7. 通用校验、执行与交付

`ActionPlanValidator` 在每个动作启动前统一检查：能力在本回合快照中存在、required permission IDs、审批、JSON Schema、文件访问、引用类型、资源状态、幂等键、依赖是否完成。失败产生可读的结构化 observation，交还给规划器或用户；不发起必然失败的调用。

`ActionGraphExecutor` 只选择依赖已满足的动作，通过既有 `call_capability()` 执行，依据 `resource_class/timeout_policy` 处理超时与并发，并把每次结果收敛为通用 `ResourceRef`：

```text
ResourceRef = type + id + locator + mime_type + display_name + access_scope + provenance
```

异步 capability 返回 `task` 引用而非假装同步完成。执行器通过现有任务/制品 capability 获取状态；需要发布或打开时，规划器选择对应已注册能力，仍经同一验证器执行。绝不在 Agent 内为“图片生成完成”“知识库完成”等业务情形写专门收尾代码。

动作并发也只按通用 contract 决定：仅无副作用、声明可并发、没有数据依赖且资源配额允许的动作可并行；其余保持有序。对外部或不可信结果，执行器只把结果作为数据 observation/ResourceRef，不能把其中的文本提升为新的系统指令。每次尝试记录规范化参数 hash 与结果 hash；按通用 idempotency/side effect contract 阻止“同参连续失败”和“无进展重复调用”，而不是针对某个工具名写停机规则。

### 8. 重启、断连与副作用安全

在一次模型规划完成后、每个动作状态变化后和每个外部调用前后，写入现有 `agent_checkpoints`。checkpoint 至少保存：`catalog_hash`、规范化 catalog 摘要、ActionPlan、每个 action 的状态/attempt/idempotency_key、observations、ResourceRef、SSE cursor、模型使用量和 workflow link。

续跑规则：

1. 读取 checkpoint，不重新执行 `completed` 动作。
2. 对 `running` 动作以 idempotency key 查询已有账本/下游状态；能确认已完成则收敛结果，无法确认的有副作用动作进入审批/人工确认，不盲目重发。
3. 对 live registry 重新计算 hash。未变化则继续；变化时只允许完成不受影响的动作，受影响动作带着差异 observation 重新规划，禁止按旧 schema 调用。
4. `agent_tool_calls` 是动作外部调用的持久账本；进程内只保存短暂执行句柄，任何多 worker 共享判断以数据库为准。

LangGraph 的 typed state/checkpoint 与 tool-call/result 成对记录、OpenCode 的 materialized registry identity 校验，分别证明这两部分是成熟工程实践；本项目直接在已有 PostgreSQL checkpoint 和 registry 上实现，不引入两者依赖。

## 精确代码落点与旧代码清理

| 区域 | 一次性改造 | 旧实现处理 |
|---|---|---|
| `backend/app/services/module_registry.py`、capability 注册契约 | 增加 `execution_contract`、数值 capability identity、规范化快照和 hash；运行时注册仍为权威 | 删除基于 `_ROLE_ORDER/min_role` 的执行授权 |
| framework auth/permission models、services、API | 增加权限目录、权限组、用户授权、capability policy、SQL scope query 与 `PrincipalContext` resolver | 角色文本仅作显示；禁止全量读取后在应用层过滤 |
| Agent experience/trajectory services | 从真实成功轨迹生成分层、脱敏 ExperiencePattern，支持 user/department/position/global 检索与晋升 | 删除旧 recipe 文本注入；经验不直接执行 |
| 各 capability 注册处及 manifest | 补齐通用 contract、检索字段与风险声明；权限要求由中央 policy 绑定数字 ID | 模块不各自复制用户权限数组，也不写 Agent 私有工具名单 |
| `modules/agent/backend/services/tool_discovery.py` | 改为 snapshot builder、catalog retriever、通用桥接；返回真实能力候选 | 移除“三元元工具是默认工具集”的 `build_tools` 语义 |
| 新增 `runtime/action_plan.py`、`runtime/action_plan_validator.py`、`runtime/action_graph_executor.py` | 定义 Pydantic plan/ref schema、校验与 DAG 执行 | 不建立第二个 loop 或业务路由器 |
| `conversation_runtime.py` | 在现有入口组装 snapshot/retrieval/planner，续跑时恢复 checkpoint 状态 | 不再在 normal/resume 路径直接重建未固定工具列表 |
| `tool_loop_runtime.py` | 收敛为唯一的模型规划、执行、SSE、replan 循环 | 删除旧的默认 `skill_list -> skill_describe -> skill_use` 驱动路径 |
| `intent_preflight.py` | 仅保留通用澄清、风险、预算和证据边界 | 删除 `first_actions`、按业务分类的工具提示和工具名建议 |
| `tool_discovery.py` 的 `content__write_ir` 专用处理 | 将 input validation/repair policy 写入 capability contract，或在 content capability 内自行完成 | 删除 Agent 对 `content__write_ir` 的名称判断与专用 LLM 修复循环 |
| `task_sink.py` | 使用 output schema/ResourceRef 生成完成证据和用户可见摘要 | 删除按工具名关键词判断读写、制品的逻辑 |
| `checkpointer.py`、`agent_tool_calls`、workflow ledger | 保存 plan/snapshot/action/ref/重试和交付事实，补齐 owner/conversation/effective capability/catalog hash | 不新增平行审计表；历史 null 数据保持可读 |
| `context_pipeline.py`、`context_injectors/workflow_recipe.py`、`workflow_recipe_service.py`、post-turn hooks、handlers/tests/models/init DDL | 移除 recipe 注入、挖掘、表和无引用代码；历史成功经验继续走现有 experience/trajectory 检索 | 不保留“最短工具链”文本暗中指挥模型 |
| `dev_toolkit/agent_runtime_tools.py` | 读取新的快照/计划/动作指标，按 owner 精确诊断 | 保持只读，不写用户会话或配置 |

数据库变更使用前向迁移：先将旧 recipe 数据导出为不可执行的历史审计（仅在确有保留价值时），同一发布中移除所有调用点并 drop `agent_workflow_recipes`。不能保留一张仍被运行时读取的旧表作为“兼容方案”。

## 工程化约束

- 计划与能力目录必须是 Pydantic/JSON Schema 对象；禁止以 prompt 文本、正则关键词或工具名 `if/else` 作为执行协议。
- capability 默认对已登录用户可见，只有中央 capability policy 明确绑定 permission IDs 时才额外限制；任何对象级权限仍由资源所有者模块强制执行。
- LLM 不是权限边界。未经 SQL/服务层授权的 capability、经验、记忆、数据摘要和资源引用一律不得进入 prompt、tool schema、observation 或 checkpoint。
- 角色、部门、岗位和权限是四个不同概念。部门/岗位默认只参与记忆检索与个性化，不自动成为权限或工具排序权重。
- 通用动作路径和个人偏好必须分库存储；任何全局/部门经验都不得包含其他用户的资源 ID、原始内容或私人偏好。
- 所有跨模块动作只经 `call_capability()`；`file_id` 读取仍先过 framework file access 检查，绝不持久化物理绝对路径。
- 每个 capability 的资源与超时由其通用 contract 声明。知识库候选检索、云端 LLM/VLM、GPU 工作等不再被 Agent 的单一快速超时混淆。
- 计划器与执行器可横向扩展，因为 checkpoint、调用账本和 snapshot 都持久化；不能依赖进程内 dict 作为共享状态。
- 审批、权限、暂停、额度、模型健康等在调用前判断；调用后错误只作为最终兜底和诊断证据。
- 日志和 UI 展示底层真实 capability 与 `ResourceRef`，不是桥接工具名；敏感参数按现有脱敏规则写账本。
- 不引入 LangGraph、Hermes、OpenCode、Dify 的运行时依赖。Dify 的 typed tool schema/trace 和 Hermes 的桥接审计只作为设计参照。

## 验收标准

### 自动化与契约

1. 对当前真实失败样本建立回归集：知识库检索超时、文件 ID 类型、JPG 文本读取、权限拒绝、能力漂移、异步制品交付；每类至少一条来自已脱敏轨迹的固定输入/期望。
2. capability snapshot、hash、权限 ID 过滤、语义/词法/引用兼容混合检索、ActionPlan schema、引用绑定、审批和 stale snapshot 均有纯单元测试。真实回归集目标 capability 的 Recall@8 不低于 95%，MRR 不低于 0.75；没有命中时必须给出各路召回分与过滤原因。
3. 执行器覆盖单动作、依赖 DAG、超时、可恢复失败重规划、不可重试副作用、provider 暂停、断连恢复和进程重启恢复；重启后不重复执行已完成的副作用动作。
4. 对每个已注册 Agent 可调用 capability 自动核验：execution contract 可解析、schema 与 manifest/runtime 不漂移、无业务名称特判；中央权限 policy 引用的 capability ID 和 permission ID 必须真实存在。
5. 权限迁移自动核验 208 个现有 public actions：无遗漏、无未知角色、对象级守卫测试不退化；普通用户默认能力与明确受限能力的清单可审计。
6. `PrincipalContext` 在未启用组织架构时稳定返回空组织字段；两个用户的个人记忆、catalog snapshot 和工具轨迹不能串用。
7. 权限撤销、部门变更、共享取消和 plan 续跑测试必须证明旧 snapshot/cache 失效；未授权 capability/schema/经验/数据进入 LLM 的数量必须为 0。
8. experience 检索覆盖全局/部门/岗位/个人/会话可见性、同义目标命中、contract 失效、失败降权、跨用户脱敏和高风险晋升审核；不可见作用域命中数必须为 0。
9. `agent` sandbox、相关 backend pytest、Ruff、`docs_audit`、`capability_contract_diff` 和 live `probe/call_capability` 全部通过。

### 真实流程

用可清理 marker 的真实文件/制品与现有 live stack 验证：

1. 文件定位并打开：规划器从能力目录选择搜索与打开，得到授权 `file` 引用。
2. 文件转换/创作：规划器依据候选能力和 schema 组合定位、转换、任务查询、发布/打开；不允许任何图片专用分支存在于 Agent runtime。
3. 知识库检索：使用该能力自己的 contract 超时，先返回已有候选；不再被 18 秒通用快超时直接截断。
4. 缺少目标 permission ID 的用户在执行前得到权限 observation；加入相应权限组后，同一用户无需改变文本 role 即可执行。
5. 云端 LLM/VLM 在未暂停时可发起真实任务；暂停或额度错误时计划得到可解释 observation，不产生无限重试。
6. 改能力 schema/临时撤销能力后，从 checkpoint 续跑会检测 hash 差异并重新规划，而不是沿用旧调用。
7. 两个用户完成同类任务后，第二个用户可命中已发布的全局/部门 action pattern，但看不到第一个用户的文件、参数偏好或原始对话。
8. 用户先生成计划再被撤销权限时，续跑在 SQL/执行闸门被拒绝；模型上下文中不包含已撤销 capability 的 schema 或先前未授权结果。

### 量化完成门槛

- 元工具调用占比从当前 80.6% 降至不高于 15%；正常已命中请求为 0 次桥接工具调用。
- 真实对话回归集 capability Recall@8 不低于 95%，且一次正常请求只需一次规划 LLM 调用即可选中工具并产出可执行计划。
- 已有兼容成功经验的请求，首次规划可执行率不低于 90%，平均探索性工具调用数比无经验基线降低至少 50%。
- 图片送入文本读取、文件 ID 类型错误、同回合 capability drift 均为 0。
- 知识库候选检索不再因 18 秒通用超时整轮失败；超时时保留已取得 observation。
- 计划、动作、结果引用和失败原因可从一个 conversation/owner 精确回溯；不混入其他用户账本。
- 仓库内不存在仍被主链路调用的 workflow recipe 注入、默认三元元工具循环或业务能力 `if/else` 路由。
- capability 授权链路不存在 `admin/editor/viewer` 大小比较；运行态只判断数值 permission IDs、审批和对象级访问。
- 权限泄露门槛为 0：未授权工具名称/schema、经验内容、记忆、资源摘要和原始结果均不得进入模型上下文或返回给用户。

## 参考调研结论

| 参考实现 | 已采纳的机制 | 不直接照搬的部分 |
|---|---|---|
| Hermes Agent `tools/tool_search.py` | 目录每次从真实工具集重建、核心安全能力常驻、按需搜索/描述/调用桥接、轨迹展示底层能力 | 会话内目录缓存、把桥接作为常规起点、其插件/MCP 运行时 |
| LangGraph `ToolNode` / PostgreSQL checkpoint | typed state、工具调用与结果成对、middleware、持久化恢复 | 不增加 LangGraph 依赖或并行图运行时 |
| OpenCode `ToolRegistry.materialize` | 每次 materialize 后以 identity 拒绝 stale tool call、按权限过滤 | 不复制其 Effect/TypeScript 基础设施 |
| Dify Agent runner | 真实 typed tool schema、循环 trace 与回调 | 不复制另一个 Agent runner 或 provider 管理层 |

本地 Hermes 源码已存在于 `/Users/hekunhua/Documents/Agent/reference_sources/10_agent_platform_reference/2026_06_25_agent_platforms/hermes-agent`，无需下载，也没有使用 4780 端口进行任何重复拉取。

## 当前执行决策

这份文档是 Agent 重构的唯一规格。实现时必须按上面的删除/替换边界一次性切换；旧链路不保留 feature flag、兼容入口或长期双写。`agent_runtime_snapshot` 作为日常巡检入口继续保留，并在重构后以新账本字段验证真实效果。
