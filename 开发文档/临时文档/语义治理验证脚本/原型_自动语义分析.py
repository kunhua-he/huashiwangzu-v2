# -*- coding: utf-8 -*-
"""自动语义分析工作流原型(领域无关,不硬编码类型)。
两步:①LLM自动发现类型体系(本体) ②LLM归类+认噪音+合并别名。
同批数据测 本地qwen vs deepseek,验证算法+对比智商。owner_id=4。"""
import asyncio, json, sys, time, re, urllib.request
sys.path.insert(0, "backend"); sys.path.insert(0, ".")

# ============ 本地模型模板层(可复用,每个模型单独适配端点+格式) ============
LOCAL_MODEL_TEMPLATES = {
    "qwen2.5-14b": {
        "endpoint": "http://127.0.0.1:11434/api/chat",  # ollama原生端点
        "model": "qwen2.5-14b:latest",
        "temperature": 0.1,
        "parse": lambda d: d.get("message", {}).get("content", ""),
    },
    "gemma-4-26b": {
        "endpoint": "http://127.0.0.1:11434/api/chat",
        "model": "gemma-4-26b:latest",
        "temperature": 0.1,
        "parse": lambda d: d.get("message", {}).get("content", ""),
    },
}

def local_chat(model_key: str, system: str, user: str, timeout=180):
    tpl = LOCAL_MODEL_TEMPLATES[model_key]
    body = json.dumps({
        "model": tpl["model"],
        "messages": [{"role":"system","content":system},{"role":"user","content":user}],
        "stream": False,
        "options": {"temperature": tpl["temperature"]},
    }).encode()
    req = urllib.request.Request(tpl["endpoint"], data=body, headers={"Content-Type":"application/json"})
    t0 = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            d = json.load(r)
        return round((time.perf_counter()-t0)*1000), tpl["parse"](d), None
    except Exception as e:
        return round((time.perf_counter()-t0)*1000), "", str(e)[:200]

# 40个真实实体切片(带当前错误分类,作对照)
SLICE = [
    "积雪草苷","积雪草甙","积雪草甘","羟基积雪草苷","积雪草提取物","积雪草叶提取物","积雪草","野生积雪草",
    "积雪草精萃","4重积雪草精粹","积雪草修护","积雪草系列","积雪草面霜","积雪草面霜2.0","积雪草主视觉","玻璃皿中的积雪草叶",
    "烟酰胺","烟酰","美白","保湿","修护","敏感肌","面膜","精华","套装","俏小喵",
    "什么","需要","日常使用","修护功效","使用效果","店里",
    "一种积雪草提取物的脱色方法","积雪草提取物相关专利",
]

def robust_json(text: str):
    """鲁棒解析LLM返回的JSON(处理markdown包裹/前后噪音)。可复用模板层。"""
    if not text: return None
    t = text.strip()
    t = re.sub(r"^```(?:json)?\s*", "", t); t = re.sub(r"\s*```$", "", t)
    # 找第一个 { 或 [ 到最后一个 } 或 ]
    for opener, closer in (("{","}"),("[","]")):
        i, j = t.find(opener), t.rfind(closer)
        if i != -1 and j > i:
            try: return json.loads(t[i:j+1])
            except Exception: pass
    return None

def call_model(profile: str, system: str, user: str, timeout=180):
    return local_chat(profile, system, user, timeout)

ONTOLOGY_SYS = "你是知识库本体分析专家。分析给定实体词,归纳出这个知识库的语义类型体系。不要套用固定行业模板,完全根据实际数据归纳。只输出JSON。"
ONTOLOGY_USER = """下面是从某企业知识库抽取的实体词(可能含噪音/分词碎片):
{names}

请归纳这个知识库的语义类型体系。输出严格JSON(数组,不要嵌套对象):
{{"types":[{{"名称":"类型名","定义":"一句话","示例":["词1","词2"]}}],"噪音判据":"什么样的词算噪音(非真实体,如疑问词/分词碎片/动词短语)"}}"""

CLASSIFY_SYS = "你是知识库实体归类专家。根据给定类型体系,给每个词判定语义类型、是否真实体、规范名。只输出JSON数组。"
CLASSIFY_USER = """类型体系:
{types}

给下面每个词判定,输出严格JSON数组(每个元素):
{{"词":"原词","是实体":true/false,"类型":"类型名或null","规范名":"用于合并同义词,如积雪草苷/积雪草甙/积雪草甘都规范成积雪草苷"}}

词列表:
{names}
只输出JSON数组。"""

def _types_list(onto):
    """兼容 onto 是 {"types":[...]} 或直接是 [...] 的情况。"""
    if isinstance(onto, dict):
        return onto.get("types") or onto.get("类型") or []
    if isinstance(onto, list):
        return onto
    return []

def run(profile: str):
    print(f"\n{'='*72}\n模型: {profile}\n{'='*72}")
    dt1, c1, e1 = call_model(profile, ONTOLOGY_SYS, ONTOLOGY_USER.format(names="、".join(SLICE)))
    onto = robust_json(c1)
    types = _types_list(onto)
    print(f"[类型发现] {dt1}ms err={e1}")
    if types:
        for t in types:
            if isinstance(t, dict):
                print(f"  类型:{t.get('名称') or t.get('name')} — {str(t.get('定义') or t.get('定义','')):.30} 例:{t.get('示例',[])[:3]}")
        if isinstance(onto, dict):
            print(f"  噪音判据: {str(onto.get('噪音判据',''))[:70]}")
    else:
        print(f"  解析失败,原文:{c1[:300]}"); return
    types_str = json.dumps(types, ensure_ascii=False)
    dt2, c2, e2 = call_model(profile, CLASSIFY_SYS, CLASSIFY_USER.format(types=types_str, names="、".join(SLICE)))
    cls = robust_json(c2)
    if isinstance(cls, dict):
        cls = cls.get("结果") or cls.get("items") or next((v for v in cls.values() if isinstance(v, list)), None)
    print(f"\n[归类] {dt2}ms err={e2}")
    if isinstance(cls, list):
        for item in cls:
            if not isinstance(item, dict): continue
            flag = "" if item.get("是实体") else " ✗噪音"
            print(f"  {str(item.get('词','')):<20} → {str(item.get('类型')):<10} 规范名={item.get('规范名','')}{flag}")
    else:
        print(f"  解析失败,原文:{c2[:300]}")

def main():
    for profile in ["qwen2.5-14b", "gemma-4-26b"]:
        try:
            run(profile)
        except Exception as e:
            print(f"{profile} 整体失败: {e}")

if __name__ == "__main__":
    main()
