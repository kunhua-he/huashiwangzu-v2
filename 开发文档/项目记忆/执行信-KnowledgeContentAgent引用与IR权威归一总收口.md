# 执行信：Knowledge / Content / Agent 引用与 IR 权威归一总收口

## 任务定位

这是一封“大信”，目标是一次性处理当前 P1 中最核心的架构重复问题：Knowledge、ContentPackage/Content IR、Agent references/artifacts 三套结构重复、来源解释重复、产物元数据重复。

不要只修单点字段；要把“权威来源在哪里、谁引用谁、前端怎么展示、后端怎么校验、测试怎么证明”一条线摸到底。

## 当前已知背景

已完成：

```text
Knowledge lifecycle debt: PASS
ContentPackage lifecycle debt: PASS
Test data pollution: PASS
Capability drift: PASS
ReleaseGate preflight: PASS_WITH_DEBT，无 blocker
README acceptance matrix: missing=0
Component key contracts: issues=0
```

审计报告指出主要 P1：

```text
Knowledge 越界耦合框架/Content 表
Content IR 权威重复
引用/产物结构重复
Agent workflow 表为空，真实工作流样本不足
```

## 总目标

建立一个清晰的权威结构：

```text
Source File / Uploaded File
→ Parser Output / Content IR
→ ContentPackage / Artifact
→ Knowledge Document / Chunk
→ Agent Evidence Reference / Tool Result / Workflow Artifact
→ Frontend Card / Clickback / Download / Open Source
```

每一层只做自己的事，不重复造轮子；跨模块只能走 capability / framework API。

## 范围

重点目录：

```text
backend/app/services/content/
backend/app/routers/content.py
backend/app/schemas/content_package.py
modules/knowledge/backend/
modules/knowledge/frontend/
modules/agent/backend/
modules/agent/frontend/components/
modules/agent/README.md
modules/knowledge/README.md
```

谨慎修改：

```text
backend/app/models/
backend/app/services/module_registry.py
```

不允许：

```text
模块之间直接 import 业务代码
Knowledge 直接读写 Content 业务表来绕过框架接口
Agent 直接 import Knowledge/Content 模块实现
```

## 必做需求

### A. 权威数据结构

1. 明确 `Content IR` 的最小权威结构：
   - `source_file_id`
   - `source_module`
   - `parser`
   - `blocks[]`
   - `assets[]`
   - `metadata`
   - `warnings[]`
   - `quality`
2. 明确 `EvidenceReference` 的最小权威结构：
   - `source_module`
   - `file_id?`
   - `document_id?`
   - `chunk_id?`
   - `package_id?`
   - `artifact_id?`
   - `page?`
   - `section?`
   - `score?`
   - `title?`
   - `snippet?`
3. 明确 `Artifact metadata` 的最小权威结构：
   - `artifact_id`
   - `package_id`
   - `source_file_id`
   - `origin_module`
   - `created_by_workflow_id?`
   - `download_url/open_url`
4. 避免 3 套结构互相复制大段内容；引用 ID + 摘要即可。

### B. 后端边界

1. Agent 获取 Knowledge 来源必须走 `knowledge` capability 或框架统一接口。
2. Knowledge 如需 ContentPackage 信息，必须通过框架公开服务或 capability，不得裸查其它模块表。
3. ContentPackage 发布 Artifact 后，要能被 Agent reference 引用。
4. 语义失败继续保持不假绿。
5. 权限必须贯通：任何 file_id / artifact_id / package_id 打开或下载都要校验 owner/share。

### C. 前端展示

1. Agent evidence card 显示统一来源：文件 / 文档 / chunk / package / artifact。
2. Knowledge 搜索结果卡片与 Agent evidence card 使用相同字段语义。
3. ContentPackage/Artifact 卡片显示来源与可回源动作。
4. 卡片至少支持：打开、下载、复制 ID、复制引用、查看原始 metadata。
5. 无法定位时显示原因，不显示假链接。

### D. 测试与验收

至少补/跑：

```text
pytest backend/tests/test_content_artifact_publish.py
pytest modules/agent/backend/tests/test_workflow_service.py
pytest modules/agent/backend/tests/test_workflow_api.py
pytest modules/knowledge/backend/tests 或现有 knowledge tests
npm --prefix frontend run build
mcp release_gate skip_ui=true mode=preflight
```

如新增测试数据，必须清理。

## 输出

写收口到：

```text
开发文档/项目记忆/KnowledgeContentAgent引用与IR权威归一总收口.md
```

收口必须包含：

```text
1. 权威结构最终定义
2. 删除/避免了哪些重复结构
3. 跨模块边界如何保证
4. 修改文件清单
5. 验收命令与结果
6. release_gate 当前结果
7. 剩余 debt / blocker
```
