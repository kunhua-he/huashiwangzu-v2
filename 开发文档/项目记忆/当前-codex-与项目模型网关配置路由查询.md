---
name: "当前 Codex 与项目模型网关配置路由查询"
type: "reference"
tags: [codex, model-gateway, config-route, reference]
agent: "codex"
created: "2026-07-02T09:18:51.872997+00:00"
---

2026-07-02 查询结果：Codex App 本地配置 ~/.codex/config.toml 当前 model_provider=codex_local_access，model=gpt-5.5，base_url=http://localhost:61462/v1，wire_api=responses，requires_openai_auth=true。项目 V2 模型网关单一配置源为 backend/data/config/models.json，DEFAULT_MODEL=deepseek-v4-flash，llm.primary=deepseek-v4-flash，provider=opencode，api_url=https://opencode.ai/zen/go/v1/chat/completions，api_key_env=DEEPSEEK_API_KEY。活接口 /api/gateway/models 返回 deepseek-v4-flash/deepseek-v4-pro/gemma-4/local-test/ollama-local；/api/gateway/health 当前 opencode/llama/local=true，ollama/mimo=false。未改代码，未记录密钥。
