# -*- coding: utf-8 -*-
"""回填自适应并发调度器。
- 纯HTTP调后端 align_entity_batch(复用常驻底座,不暴毙)
- JSON配置热修改(改回填配置.json,30秒内生效,不重启)
- 每检测间隔看CPU:高于上限→减并发,低于下限→加并发,把CPU稳在目标区间
- 线程数不硬编码,全走配置
用法: screen -dmS 回填 python 回填_自适应调度.py
"""
import asyncio, json, os, time, subprocess
import urllib.request

BASE = "/Users/hekunhua/Documents/Agent/PHP/华世王镞_v2"
CFG_PATH = os.path.join(BASE, "开发文档/临时文档/语义治理验证脚本/回填配置.json")
LOG = os.path.join(BASE, "开发文档/临时文档/语义治理验证脚本/回填_自适应.log")
API = "http://127.0.0.1:33000/api/modules/call"


def 日志(msg):
    line = f"[{time.strftime('%H:%M:%S')}] {msg}"
    print(line, flush=True)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def 读配置():
    try:
        with open(CFG_PATH, encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        日志(f"读配置失败,用默认: {e}")
        return {"目标CPU百分比": 82, "CPU上限": 85, "CPU下限": 78, "最小并发": 1,
                "最大并发": 16, "初始并发": 4, "每并发批量": 20, "gate开关": True,
                "检测间隔秒": 30, "暂停": False}


def 生成token():
    out = subprocess.run(
        [f"{BASE}/backend/venv/bin/python3.14",
         f"{BASE}/开发文档/临时文档/语义治理验证脚本/_生成token.py"],
        cwd=BASE, capture_output=True, text=True,
    )
    for ln in reversed(out.stdout.strip().splitlines()):
        if ln.count(".") == 2 and len(ln) > 50:
            return ln.strip()
    return ""


def 取CPU():
    """整机CPU使用率(%,32核平均)。用 top -l 2 取第二次采样的 idle。
    (iostat -c 末列是负载值不是idle,别用。)"""
    try:
        out = subprocess.run(["top", "-l", "2", "-n", "0"], capture_output=True, text=True, timeout=10).stdout
        # 取最后一行 "CPU usage: X% user, Y% sys, Z% idle"
        cpu_lines = [l for l in out.splitlines() if "CPU usage" in l]
        if not cpu_lines:
            return 50.0
        import re
        m = re.search(r"([\d.]+)%\s*idle", cpu_lines[-1])
        if m:
            return round(100 - float(m.group(1)), 1)
        return 50.0
    except Exception:
        return 50.0


TOKEN = [""]


def 打一批(batch, gate, batch_conc=16):
    body = json.dumps({
        "target_module": "knowledge", "action": "align_entity_batch",
        "parameters": {"batch": batch, "gate": gate, "batch_conc": batch_conc, "shard": 0, "shards": 1},
    }).encode()
    req = urllib.request.Request(API, data=body, headers={
        "Content-Type": "application/json", "Authorization": f"Bearer {TOKEN[0]}"})
    try:
        raw = urllib.request.urlopen(req, timeout=120).read()
        d = json.loads(raw)
        dd = d.get("data", {}).get("data", {})
        if "remaining" in dd:
            return dd.get("checked", 0), dd.get("aligned", 0), dd.get("remaining", -1)
        # session过期→重生成token
        if "expired" in str(d.get("error", "")).lower():
            TOKEN[0] = 生成token()
        return 0, 0, -1
    except Exception:
        return 0, 0, -1


# 共享状态:目标并发 + 全局停止
状态 = {"目标并发": 1, "batch": 40, "gate": True, "batch_conc": 16, "停止": False, "remaining": -1}


async def 一个worker(序):
    """worker按序号自查:序号≥目标并发时自己退出(实现降并发)。"""
    loop = asyncio.get_event_loop()
    while not 状态["停止"]:
        if 序 >= 状态["目标并发"]:
            return  # 目标降低,高序号worker退出
        checked, aligned, remaining = await loop.run_in_executor(
            None, 打一批, 状态["batch"], 状态["gate"], 状态["batch_conc"])
        if remaining == 0:
            状态["停止"] = True
            return
        if remaining >= 0:
            状态["remaining"] = remaining
        if checked == 0:
            await asyncio.sleep(3)  # 异常/token过期,缓一下


async def main():
    TOKEN[0] = 生成token()
    cfg = 读配置()
    状态["目标并发"] = cfg["初始并发"]
    状态["batch"] = cfg["每并发批量"]
    状态["gate"] = cfg["gate开关"]
    状态["batch_conc"] = cfg.get("批内并发", 16)
    日志(f"自适应回填启动. 初始并发={状态['目标并发']} 目标CPU={cfg['目标CPU百分比']}% 上限{cfg['CPU上限']}下限{cfg['CPU下限']}")

    tasks = {}

    def 同步worker数():
        # 补齐到目标并发(退出的补新的,序号复用)
        for 序 in range(状态["目标并发"]):
            if 序 not in tasks or tasks[序].done():
                tasks[序] = asyncio.create_task(一个worker(序))

    同步worker数()

    while not 状态["停止"]:
        await asyncio.sleep(cfg["检测间隔秒"])
        cfg = 读配置()
        状态["batch"] = cfg["每并发批量"]
        状态["gate"] = cfg["gate开关"]
        状态["batch_conc"] = cfg.get("批内并发", 16)
        if cfg.get("暂停"):
            日志("配置暂停"); 状态["停止"] = True; break
        cpu = 取CPU()
        活跃 = sum(1 for t in tasks.values() if not t.done())
        旧 = 状态["目标并发"]
        if cpu > cfg["CPU上限"]:
            状态["目标并发"] = max(cfg["最小并发"], 状态["目标并发"] - 1)
        elif cpu < cfg["CPU下限"]:
            状态["目标并发"] = min(cfg["最大并发"], 状态["目标并发"] + 1)
        同步worker数()
        动作 = f"{旧}→{状态['目标并发']}" if 旧 != 状态["目标并发"] else "保持"
        日志(f"CPU={cpu}% 活跃={活跃} 剩余={状态['remaining']} 并发{动作}")
        if 状态["remaining"] == 0:
            日志("★全部完成"); 状态["停止"] = True; break

    await asyncio.gather(*tasks.values(), return_exceptions=True)


if __name__ == "__main__":
    asyncio.run(main())
