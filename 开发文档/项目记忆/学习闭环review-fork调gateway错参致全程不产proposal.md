---
name: "学习闭环review fork调gateway错参致全程不产proposal"
type: gotcha
tags: ["agent", "review-fork", "gateway", "gotcha", "verification"]
created: 2026-06-25
agent: claude
---

Agent升级03 Background Review Fork: review_service.run_background_review 调 gateway_service.chat() 用了错参 model_profile=, 实际签名是 profile_key=。导致每次review模型调用抛 "chat() got an unexpected keyword argument 'model_profile'", 被 _safe_run/try-except 吞成 WARNING, review任务全卡pending、agent_review_results=0 —— 学习闭环(03核心)自始至终没通过一次, 一条proposal都没产。执行agent报告判"通过"(它只看任务创建/表存在, 没查results行数或日志)。小马仔真数据验收(查review_tasks全pending+results=0+grep agent.log)抓出。修: model_profile→profile_key, 真对话后产出stable_rule proposal。教训: ①调框架能力前用 capabilities/读签名查准参数名(别凭记忆); ②被try/except吞的WARNING是验收盲区, 凡"后台/异步产物"必查产物表行数+日志exception, 不能只看"任务建了/表在"。关联 [[运行时重构遗留-stuck-detector漏owner-id致db插入崩]](同类:执行agent报告通过但活系统真跑崩/不产)。
