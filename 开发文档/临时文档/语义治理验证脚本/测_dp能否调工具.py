# -*- coding: utf-8 -*-
"""地基验证:deepseek(走opencode网关)能不能真回传 tool_calls。
给它一个"查词频"工具,让它判"华世王族公司→华世王镞公司"该不该并。
只看:① 它会不会主动发起 tool_call ② 回传结构对不对。纯测试不写库。
"""
import asyncio, sys, json
sys.path.insert(0, "backend"); sys.path.insert(0, ".")

TOOLS = [{
    "type": "function",
    "function": {
        "name": "查词频",
        "description": "查某个词在本知识库干净文本层(100%正确的原文)出现在多少篇文档里。返回篇数(整数)。篇数高=该词是库里真实存在的权威写法;篇数0=库里根本没这个词。",
        "parameters": {
            "type": "object",
            "properties": {"词": {"type": "string", "description": "要查的词"}},
            "required": ["词"],
        },
    },
}]

SYS = (
    "你是中文实体校对专家。判断【原词】是不是【候选词】的错别字误写(该并),还是本身就是独立正常词(该留)。\n"
    "你不知道哪个词是正确的——你必须用【查词频】工具查证据:\n"
    "候选词篇数高、原词篇数0 → 候选词是库里权威写法,原词是它的变体误写 → 判【并】\n"
    "拿不准就多查几次。查完再下结论,只输出JSON: {\"判定\":\"并\"或\"留\",\"因\":\"简短\"}"
)


async def main():
    from app.gateway.router import gateway_router
    msgs = [
        {"role": "system", "content": SYS},
        {"role": "user", "content": "原词:华世王族公司\n候选词:华世王镞公司\n先用工具查证据,再判该并还是该留。"},
    ]
    res = await gateway_router.chat(msgs, profile_key="deepseek-v4-flash", tools=TOOLS)
    print("=== 第一轮返回 ===", flush=True)
    print("content:", repr(res.get("content", ""))[:200], flush=True)
    print("finish_reason:", res.get("finish_reason"), flush=True)
    print("tool_calls:", json.dumps(res.get("tool_calls", []), ensure_ascii=False)[:500], flush=True)
    tc = res.get("tool_calls") or []
    if tc:
        print(f"\n✓ deepseek 主动发起了 {len(tc)} 次工具调用 —— 真 function calling 可用", flush=True)
    else:
        print("\n✗ 没发起工具调用(可能provider不支持或直接答了) —— 走代码取证路线", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
