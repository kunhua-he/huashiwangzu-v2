# -*- coding: utf-8 -*-
"""全库混沌样本验证:gemma在154个千奇百怪真实实体上自动发现类型+归类。
不死磕积雪草,看算法在混沌数据(专利/地址/人名/事件/乱码/碎片)上是否翻车。"""
import json, time, re, urllib.request

SAMPLE = json.load(open("开发文档/临时文档/_混沌样本.json", encoding="utf-8"))
NAMES = [x["name"] for x in SAMPLE]
CUR_CAT = {x["name"]: x["cat"] for x in SAMPLE}

MODEL = "gemma-4-26b:latest"
EP = "http://127.0.0.1:11434/api/chat"

def robust_json(text):
    if not text: return None
    t = re.sub(r"^```(?:json)?\s*","",text.strip()); t = re.sub(r"\s*```$","",t)
    for o,c in (("[","]"),("{","}")):
        i,j = t.find(o), t.rfind(c)
        if i!=-1 and j>i:
            try: return json.loads(t[i:j+1])
            except Exception: pass
    return None

def chat(system, user, timeout=240):
    body = json.dumps({"model":MODEL,"messages":[{"role":"system","content":system},{"role":"user","content":user}],"stream":False,"options":{"temperature":0.1}}).encode()
    req = urllib.request.Request(EP, data=body, headers={"Content-Type":"application/json"})
    t0=time.perf_counter()
    with urllib.request.urlopen(req, timeout=timeout) as r: d=json.load(r)
    return round((time.perf_counter()-t0)*1000), d.get("message",{}).get("content","")

# 阶段A:自动发现类型体系(从混沌全样本,不从积雪草)
ONTO_SYS = "你是知识库本体分析专家。从给定实体词自动归纳这个知识库的语义类型体系,不套固定行业模板。只输出JSON。"
ONTO_USER = """下面是从某企业知识库随机抽取的实体词(含大量噪音/碎片/乱码,真实混杂):
{names}

归纳覆盖这些数据的语义类型体系。输出严格JSON(数组):
[{{"名称":"类型名","定义":"一句话","示例":["词1","词2"]}}]
要求:类型要能覆盖真实内容(成分/功效/产品/品牌/人物/地点/机构/事件/时间/技术专利/规格等按实际需要),并单独有一个类型表示"噪音/非实体"(疑问词/分词碎片/OCR乱码/无意义短语)。"""

CLS_SYS = "你是实体归类专家。按给定类型给每个词判定。只输出JSON数组,不解释。"
CLS_USER = """类型体系:
{types}

给每个词输出:{{"词":"原词","类型":"类型名","是实体":true/false,"规范名":"同义词归一后的标准名"}}
词:
{names}
只输出JSON数组。"""

def main():
    print(f"混沌样本 {len(NAMES)} 个。模型 {MODEL}")
    dt1,c1 = chat(ONTO_SYS, ONTO_USER.format(names="、".join(NAMES)))
    onto = robust_json(c1)
    print(f"\n[阶段A 自动发现类型] {dt1}ms")
    if not isinstance(onto, list):
        print("解析失败:", c1[:300]); return
    for t in onto:
        if isinstance(t,dict): print(f"  {t.get('名称')}: {str(t.get('定义',''))[:28]} 例{t.get('示例',[])[:2]}")
    # 阶段B 分批归类(每批40)
    types_str = json.dumps(onto, ensure_ascii=False)
    allcls=[]
    for i in range(0, len(NAMES), 40):
        batch = NAMES[i:i+40]
        dt2,c2 = chat(CLS_SYS, CLS_USER.format(types=types_str, names="、".join(batch)))
        cls = robust_json(c2)
        if isinstance(cls, dict): cls = next((v for v in cls.values() if isinstance(v,list)), [])
        if isinstance(cls, list): allcls.extend(cls)
        print(f"  [归类批{i//40+1}] {dt2}ms 累计{len(allcls)}")
    # 汇总:按类型分组 + 噪音统计 + 合并统计
    from collections import defaultdict
    bytype=defaultdict(list); noise=[]; merged=[]
    for it in allcls:
        if not isinstance(it,dict): continue
        w=str(it.get("词","")); ty=str(it.get("类型")); canon=str(it.get("规范名",""))
        if not it.get("是实体"): noise.append(w)
        else: bytype[ty].append(w)
        if canon and canon!=w and it.get("是实体"): merged.append(f"{w}→{canon}")
    print(f"\n{'='*60}\n[结果汇总] 类型{len(bytype)}类 噪音{len(noise)}个 合并{len(merged)}对")
    for ty, ws in sorted(bytype.items(), key=lambda x:-len(x[1])):
        print(f"\n  【{ty}】{len(ws)}个: {', '.join(ws[:12])}")
    print(f"\n  【判为噪音】{len(noise)}个: {', '.join(noise[:25])}")
    print(f"\n  【合并样例】: {'; '.join(merged[:15])}")
    json.dump({"onto":onto,"cls":allcls}, open("开发文档/临时文档/_混沌验证结果.json","w"), ensure_ascii=False, indent=1)

if __name__=="__main__": main()
