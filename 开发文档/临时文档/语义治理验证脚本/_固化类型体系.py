# -*- coding: utf-8 -*-
"""固化语义类型体系到 kb_semantic_types(owner_id=4)。治坑2:定死不漂移。
综合gemma两次自动发现结果+护肤品专业判断,带反例边界(治坑3)。幂等:先清后写。"""
import asyncio, sys
sys.path.insert(0, "backend"); sys.path.insert(0, ".")
from app.database import AsyncSessionLocal
from sqlalchemy import text as T

OWNER = 4
# (类型名, 定义, 示例, 反例, 是否噪音)
TYPES = [
    ("成分", "活性化学或生物成分,产品起效的分子物质", ["积雪草苷","烟酰胺","α硫辛酸","神经酰胺","视黄醇"], ["病理症状","产品名","功效"], False),
    ("原料", "植物或天然原料及其提取物形态", ["积雪草提取物","植物油","北美金缕梅提取物","积雪草叶提取物"], ["纯化学成分名","产品"], False),
    ("功效", "产品的功能、作用或使用效果", ["美白","保湿","修护","舒缓","收缩毛孔","祛痘"], ["成分","产品","肤质"], False),
    ("品类", "护肤品品类通名(非具体SKU)", ["面膜","精华","面霜","啫喱","水乳"], ["具体产品SKU","品牌"], False),
    ("产品", "具体商品/SKU(带品牌或型号)", ["积雪草面霜2.0","娇薇诗玻尿酸面膜","水感修颜霜"], ["品类通名","原料"], False),
    ("品牌", "品牌或商标标识", ["俏小喵","KRNOBQUE","娇薇诗","妍绮诗"], ["机构","产品","人物"], False),
    ("系列", "产品系列线", ["积雪草系列","清颜系列"], ["单品","品类"], False),
    ("规格", "包装、规格、套装形式", ["套装","正装","30ml","调肤套装"], ["产品名","品类"], False),
    ("肤质", "皮肤类型或适用人群特征", ["敏感肌","油痘肌","干性皮肤","问题肌"], ["功效","成分"], False),
    ("人物", "人名、角色、客户身份", ["余春萍","C级顾客","执行老师","王小姐"], ["机构","品牌"], False),
    ("组织", "企业、机构、协会", ["美容院","自然疗法协会","香港花都国际美容集团"], ["品牌","人物","地点"], False),
    ("地点", "地址、行政区域、场所空间", ["昆明","广州市新市黄边工业区","洁净实验室","门店"], ["场景描述短语"], False),
    ("事件", "真实发生的活动或事件", ["促销活动","招商会","品鉴会","入职"], ["场景描述短语","营销方案文案","疑问句"], False),
    ("时间", "日期、节假日、时间周期", ["2019-02-01","十一假期","三八妇女节"], [], False),
    ("技术标准", "专利、检测报告、安全评估、规范文件", ["专利号ZL2022","检测编号YJ-R-202412","安全评估报告"], ["普通产品"], False),
    ("视觉素材", "设计、构图、材质、色彩等视觉元素", ["积雪草主视觉","粉色芍药花朵","木纹墙面","红色LED背景"], ["真实产品","场所"], False),
    ("营销内容", "营销方案、话术、文案", ["引流裂变方案","团队激励文案","顾客调查问卷"], ["真实事件","产品"], False),
    ("噪音", "非实体:疑问词/分词碎片/OCR乱码/无意义短语/纯描述句", ["什么","需要","日常使用","使用效果","@菠萝","人生之路"], ["任何有明确指代的实体"], True),
]

async def main():
    async with AsyncSessionLocal() as db:
        await db.execute(T("DELETE FROM kb_semantic_types WHERE owner_id=:o"), {"o": OWNER})
        for i, (name, defi, ex, cex, noise) in enumerate(TYPES):
            await db.execute(T("""
                INSERT INTO kb_semantic_types(owner_id,type_name,definition,examples,counter_examples,is_noise,sort_order,status,created_at,updated_at)
                VALUES(:o,:n,:d,cast(:ex as json),cast(:cex as json),:noise,:so,'active',now(),now())
            """), {"o":OWNER,"n":name,"d":defi,"ex":__import__("json").dumps(ex,ensure_ascii=False),
                   "cex":__import__("json").dumps(cex,ensure_ascii=False),"noise":noise,"so":i})
        await db.commit()
        r = await db.execute(T("SELECT type_name,is_noise FROM kb_semantic_types WHERE owner_id=:o ORDER BY sort_order"), {"o":OWNER})
        rows = r.all()
        print(f"固化 {len(rows)} 类:")
        print("  " + " / ".join(f"{n}{'(噪音)' if x else ''}" for n,x in rows))

if __name__ == "__main__":
    asyncio.run(main())
