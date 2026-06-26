# 抖音投放助手模块交付

- **Agent**: executor（当前会话）
- **模块**: `douyin-delivery`（抖音投放助手）
- **干了啥**:
  - 从 `_template` 脚手架新建完整模块
  - 后端 5 张 `douyin_*` 表（products/scripts/ad_copies/campaigns/prompts），17 个 API 端点
  - 前端 Vue3 + Element Plus 六 Tab 页
  - 注册 3 个跨模块能力（generate_script/generate_ad_copy/validate_content）
  - 接入模型网关做 AI 生成 + 知识库做内容校验
  - 7 个默认提示词种子到 DB
- **渠道颗粒度**: local_push（本地推）/ ocean_engine（巨量引擎）/ qianchuan（千川）
- **交付**: 收件箱/业务模块-抖音投放助手/ 五件套 + 开发记录.md + README.md
- **待深化**: 前端桌面壳构建验证、sandbox 独立运行、知识库数据入库后重验校验
