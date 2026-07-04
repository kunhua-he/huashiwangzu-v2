# 执行信：真实 Workflow 种子数据与 Agent 治理面板落地

## 任务定位

这封信专门处理审计报告中的 P1：Agent workflow 表为空、治理面板缺少真实样本、很多能力只有结构没有可验证运行数据。

目标不是造假数据，而是建立可控的开发/演示 seed 与真实 workflow 可观测能力，让 Agent 工作中枢能被产品验收。

## 背景

当前 Agent 已有：

```text
workflow summary
工具调用 ledger
EvidenceReference 卡片
artifact/reference 计数
```

但审计指出：

```text
Agent workflow 表为空 / 缺少真实运行样本
治理面板难以验证真实多代理过程
```

## 总目标

建立一套“可清理、可重复、可演示、可验收”的 Agent workflow seed 与治理面板闭环：

```text
创建 demo workflow
→ 包含子代理步骤
→ 包含 tool calls
→ 包含 evidence references
→ 包含 artifacts
→ 包含 semantic failure / retry 样例
→ 前端治理面板可筛选/打开/复制/回源
→ 测试后可清理，不污染 release gate
```

## 范围

```text
modules/agent/backend/
modules/agent/frontend/
modules/agent/sandbox/
modules/agent/README.md
backend/tests 或 modules/agent/backend/tests
开发文档/项目记忆
```

如果需要框架任务队列接口，只能调用已有框架公开能力，不要改框架核心，除非是很小且必要的测试辅助。

## 必做需求

### A. Seed / Demo 数据机制

1. 增加可控 seed 能力，必须 gated：只能 admin/dev/test 调用，不能普通用户误触。
2. Seed 创建的数据必须带 marker，例如：`agent-demo-` / `workflow-demo-`。
3. Seed 必须支持 cleanup，清理 workflow、tool_call、artifact/reference 相关测试数据。
4. Seed 数据至少包含：
   - completed workflow
   - partial workflow
   - failed/semantic_failed workflow
   - needs-confirmation workflow
   - workflow with evidence references
   - workflow with artifact references
5. Seed 不得污染 test_data_pollution gate；若使用文件/包/artifact，必须 cleanup。

### B. 后端 API

1. Workflow list 支持按 status / has_failures / has_artifacts / has_references 过滤。
2. Workflow detail 返回步骤、tool calls、references、artifacts、summary counts。
3. 增加治理 summary capability/API：总数、失败数、平均耗时、待人工确认、最近错误。
4. semantic failure 必须显示 reason。
5. 权限：只能看自己的 workflow 或 admin 全局视图。

### C. 前端治理面板

1. WorkflowList 显示真实统计，不只是状态文本。
2. WorkflowDetail 显示：步骤树、工具账本、references、artifacts、错误。
3. 支持筛选：全部/失败/需确认/有产物/有引用。
4. 支持动作：打开详情、复制 workflow id、复制错误、打开 reference、打开 artifact。
5. 空态区分：真的没有 workflow vs API 失败 vs 正在加载。

### D. 验收

必须跑：

```text
pytest modules/agent/backend/tests/test_workflow_service.py
pytest modules/agent/backend/tests/test_workflow_api.py
npm --prefix frontend run build
mcp release_gate skip_ui=true mode=preflight
```

如新增 seed API，补测试：

```text
普通用户不能 seed
seed 后列表能看到
cleanup 后不残留
```

## 输出

写收口到：

```text
开发文档/项目记忆/真实Workflow种子数据与Agent治理面板落地收口.md
```

必须包含：seed 数据结构、清理方式、前端截图/描述、测试结果、剩余风险。
