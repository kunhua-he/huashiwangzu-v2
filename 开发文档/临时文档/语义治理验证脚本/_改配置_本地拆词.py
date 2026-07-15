# -*- coding: utf-8 -*-
"""加本地qwen拆词profile + knowledge routing指向它。保证json格式不坏。"""
import json
P = "backend/data/config/models.json"
c = json.load(open(P, encoding="utf-8"))

# 1. 加本地qwen拆词profile(走ollama,免费无限,不烧云端额度)
profiles = c["model_types"]["llm"]["profiles"]
profiles["qwen-local-planner"] = {
    "provider": "ollama",
    "model": "qwen2.5-14b:latest",
    "temperature": 0.1,
    "max_tokens": 1024,
    "response_adapter": "openai_compat",
    "system_prompt": "你是知识库检索查询分析器。只输出JSON，不解释。",
    "context_budget": 32000,
    "price_input": 0,
    "price_output": 0,
}

# 2. knowledge routing 加查询拆词专用profile(本地),不动agent_search_profile
kr = c["module_routing"]["knowledge"]
kr["query_planning_profile"] = "qwen-local-planner"

json.dump(c, open(P, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
print("已写入。qwen-local-planner profile + query_planning_profile=qwen-local-planner")
print("验证:", json.load(open(P,encoding="utf-8"))["model_types"]["llm"]["profiles"]["qwen-local-planner"]["model"])
