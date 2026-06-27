"""Probe: capture raw API response before adapter normalization."""

import asyncio
import json
import os
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[3] / "backend"
sys.path.insert(0, str(BACKEND_DIR))
os.environ.setdefault("APP_ENV", "development")

from app.gateway.config import MODEL_PROFILES
from app.gateway.openai_provider import OpenCodeProvider

TOOLS = [
    {"type": "function", "function": {
        "name": "get_weather",
        "description": "查某个城市的实时天气",
        "parameters": {"type": "object", "properties": {"city": {"type": "string"}}, "required": ["city"]},
    }},
    {"type": "function", "function": {
        "name": "get_time",
        "description": "查某个城市的当前时间",
        "parameters": {"type": "object", "properties": {"city": {"type": "string"}}, "required": ["city"]},
    }},
    {"type": "function", "function": {
        "name": "get_air_quality",
        "description": "查某个城市的空气质量",
        "parameters": {"type": "object", "properties": {"city": {"type": "string"}}, "required": ["city"]},
    }},
]

PROFILE_KEY = "deepseek-v4-flash"
PROFILE = MODEL_PROFILES.get(PROFILE_KEY, {})
provider = OpenCodeProvider()

async def main():
    print("Provider: opencode")
    print(f"Model: {PROFILE.get('model')}")
    print(f"URL: {provider.api_url}\n")

    cases = [
        ("单工具-中文", [{"role": "user", "content": "今天北京天气怎么样？"}]),
        ("单工具-英文", [{"role": "user", "content": "What time is it in Tokyo?"}]),
        ("并行工具", [{"role": "user", "content": "同时查北京天气、东京时间和上海空气质量"}]),
    ]

    for label, messages in cases:
        print(f"{'='*60}")
        print(f"[{label}]")
        try:
            raw = await provider.chat(
                messages=messages,
                model=PROFILE.get("model", PROFILE_KEY),
                temperature=PROFILE.get("temperature", 0.7),
                max_tokens=PROFILE.get("max_tokens", 8192),
                tools=TOOLS,
            )
            # Print the key parts
            choice = (raw.get("choices") or [{}])[0]
            msg = choice.get("message") or {}
            tc = msg.get("tool_calls")
            print(f"  finish_reason: {choice.get('finish_reason')}")
            print(f"  content: '{msg.get('content', '')[:100]}'")
            print(f"  tool_calls in message: {tc is not None}")
            if tc:
                print(f"  tool_calls count: {len(tc)}")
                for t in tc:
                    fn = t.get("function", {})
                    print(f"    id={t.get('id','')[:20]} name={fn.get('name','')}")
                    print(f"    arguments type={type(fn.get('arguments','')).__name__} = {json.dumps(fn.get('arguments',''), ensure_ascii=False)[:200]}")
            else:
                # Check full raw for tool_calls anywhere
                print(f"  RAW keys: {list(raw.keys())}")
                print(f"  choices[0] keys: {list(choice.keys())}")
                print(f"  message keys: {list(msg.keys())}")
        except Exception as e:
            print(f"  ERROR: {e}")

    print(f"\n{'='*60}")
    print("Done.")

if __name__ == "__main__":
    asyncio.run(main())
