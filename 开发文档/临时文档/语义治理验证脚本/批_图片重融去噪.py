# -*- coding: utf-8 -*-
"""存量图片重融去噪(应用 is_image 逻辑:round1像素分析剔出fused_text,归 attributes)。

双后端:云端 deepseek(网关,快)+ 本地 gemma(免费兜底)。云端计数达 CLOUD_BUDGET 或报错→切本地。
并发 CONC。可续跑(只处理 fused_text 还含噪声的页)。owner=4。
用法: python 批_图片重融去噪.py [--conc 50] [--cloud-budget 5000] [--limit N] [--dry]

注意:不改正式流程,临时脚本复用 TFUSION 提示词 + is_image 分轮逻辑。华哥授权云端压额度。
"""
import asyncio, sys, json, time, argparse, urllib.request
sys.path.insert(0, "backend"); sys.path.insert(0, ".")
from app.database import AsyncSessionLocal
from sqlalchemy import text as T
from app.gateway.router import gateway_router
from modules.knowledge.backend.services.prompt_utils import TFUSION, load_prompt_detached

OWNER = 4
CLOUD_PROFILE = "deepseek-v4-flash"
LOCAL_MODEL = "gemma-4-26b:latest"
LOCAL_EP = "http://127.0.0.1:11434/api/chat"
NOISE_KEYS = ("平均亮度", "边缘密度", "视觉轮廓", "px", "RGB", "主色")
# 本地路由 GPT(responses 协议,华哥指定)。额度恢复,主力,并发200。
GPT_EP = "http://localhost:50936/v1/responses"
GPT_MODEL = "gpt-5.5"
GPT_KEY = "agt_codex_ObOla6ZsThNlW1KdD7Ykmj5ZmH6FFkO1"

_state = {"cloud_calls": 0, "cloud_dead": False, "budget": 5000}


async def _gpt_fuse(sys_p: str, user_msg: str) -> dict | None:
    """本地路由 GPT,responses 协议。input 传 system+user 合并文本,只取 message 的 output_text(跳 reasoning)。"""
    import asyncio, json, urllib.request
    payload = json.dumps({
        "model": GPT_MODEL,
        "input": f"{sys_p}\n\n{user_msg}",
        "stream": False,
    }).encode()
    loop = asyncio.get_event_loop()
    last_exc = None
    for attempt in range(3):  # 瞬断重试(高并发防连接闪断)
        try:
            req = urllib.request.Request(GPT_EP, data=payload,
                                         headers={"Content-Type": "application/json", "Authorization": f"Bearer {GPT_KEY}"})
            raw = await loop.run_in_executor(None, lambda: urllib.request.urlopen(req, timeout=180).read())
            d = json.loads(raw)
            text = ""
            for it in d.get("output", []):
                if it.get("type") == "message":
                    text += "".join(c.get("text", "") for c in it.get("content", []) if c.get("type") == "output_text")
            return _parse(text)
        except urllib.error.HTTPError as he:
            if he.code in (401, 402, 403, 429):
                raise  # 鉴权/额度→上抛,让主逻辑标死转本地
            last_exc = he
        except Exception as e:
            last_exc = e
        await asyncio.sleep(0.5 * (attempt + 1))
    raise last_exc if last_exc else RuntimeError("gpt_fuse failed")


def _img_user_msg(ocr: str, vision: str) -> str:
    return (
        "请交叉印证以下图片的两轮采集结果，输出融合后的权威描述。\n"
        "注意:这是图片,没有文本提取层。图里的文字以 OCR 为准,画面内容以视觉描述为准。\n"
        "不要把像素尺寸/分辨率/亮度等技术元数据写进 fused_text 正文。\n\n"
        f"=== 图内文字：截图 OCR ===\n{(ocr or '(无)')[:4000]}\n\n"
        f"=== 画面内容：视觉描述 ===\n{(vision or '(无)')[:4000]}"
    )


def _parse(content: str) -> dict | None:
    if not content:
        return None
    c = content.strip()
    if c.startswith("```"):
        c = "\n".join(c.split("\n")[1:])
        if c.endswith("```"):
            c = c[:-3]
    i, j = c.find("{"), c.rfind("}")
    if i != -1 and j > i:
        try:
            return json.loads(c[i:j + 1])
        except Exception:
            return None
    return None


async def _local_fuse(sys_p: str, user_msg: str) -> dict | None:
    body = json.dumps({
        "model": LOCAL_MODEL,
        "messages": [{"role": "system", "content": sys_p}, {"role": "user", "content": user_msg}],
        "stream": False, "options": {"temperature": 0.2},
    }).encode()
    req = urllib.request.Request(LOCAL_EP, data=body, headers={"Content-Type": "application/json"})
    loop = asyncio.get_event_loop()
    raw = await loop.run_in_executor(None, lambda: urllib.request.urlopen(req, timeout=120).read())
    return _parse(json.loads(raw).get("message", {}).get("content", ""))


async def fetch_noisy_pages(limit=None):
    """含像素噪声的图片页 + 该页 OCR(round2)/VLM(round3)/技术属性(round1)。"""
    noise_sql = " OR ".join(f"pf.fused_text LIKE '%{k}%'" for k in NOISE_KEYS)
    lim = f"LIMIT {int(limit)}" if limit else ""
    async with AsyncSessionLocal() as db:
        r = await db.execute(T(f"""
            SELECT pf.document_id, pf.page,
              max(CASE WHEN rd.round=2 THEN rd.content END) AS ocr,
              max(CASE WHEN rd.round=3 THEN rd.content END) AS vision,
              max(CASE WHEN rd.round=1 THEN rd.content END) AS tech
            FROM kb_page_fusions pf
            JOIN kb_documents d ON d.id=pf.document_id
            LEFT JOIN kb_raw_data rd ON rd.document_id=pf.document_id AND rd.page=pf.page AND rd.owner_id=4
            WHERE pf.owner_id=4 AND d.extension IN ('jpg','png','jpeg','webp','gif','bmp')
              AND ({noise_sql})
              AND EXISTS (SELECT 1 FROM kb_raw_data rd2 WHERE rd2.document_id=pf.document_id
                          AND rd2.page=pf.page AND rd2.owner_id=4 AND rd2.round IN (2,3)
                          AND length(coalesce(rd2.content,''))>10)
            GROUP BY pf.document_id, pf.page
            ORDER BY pf.document_id, pf.page {lim}
        """))
        return [(int(d), int(p), o, v, t) for d, p, o, v, t in r.all()]


async def main(conc, budget, limit, dry):
    import importlib
    mod = importlib.import_module("批_图片重融去噪")
    m2 = importlib.import_module("批_图片重融去噪_2")
    mod._state["budget"] = budget
    sys_p = await load_prompt_detached(TFUSION)
    pages = await fetch_noisy_pages(limit)
    print(f"待重融图片页: {len(pages)}, 并发={conc}, 云端预算={budget}, dry={dry}", flush=True)
    sem = asyncio.Semaphore(conc)
    stat = {"cloud": 0, "local": 0, "fail": 0}
    t0 = time.time()
    done = 0

    async def worker(pg):
        nonlocal done
        d, p, ocr, vision, tech = pg
        async with sem:
            used = await m2.refuse_one(sys_p, d, p, ocr, vision, (tech or "").strip(), mod, dry)
            stat[used] = stat.get(used, 0) + 1
            done += 1
            if done % 100 == 0:
                print(f"...{done}/{len(pages)} 云{stat['cloud']} 本地{stat['local']} 失败{stat['fail']} "
                      f"云调用{mod._state['cloud_calls']} 用时{time.time()-t0:.0f}s", flush=True)

    await asyncio.gather(*(worker(pg) for pg in pages))
    print(f"\n完成: 云{stat['cloud']} 本地{stat['local']} 失败{stat['fail']} "
          f"云调用总{mod._state['cloud_calls']} 用时{time.time()-t0:.0f}s", flush=True)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--conc", type=int, default=50)
    ap.add_argument("--cloud-budget", type=int, default=5000)
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--dry", action="store_true")
    a = ap.parse_args()
    asyncio.run(main(a.conc, a.cloud_budget, a.limit, a.dry))
