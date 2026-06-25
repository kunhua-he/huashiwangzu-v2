import json
import logging

logger = logging.getLogger("v2.agent").getChild("_utils")


def j(obj) -> str:
    return json.dumps(obj, ensure_ascii=False, default=str)


def tool_calls_for_history(tool_calls: list[dict]) -> list[dict]:
    normalized = []
    for item in tool_calls:
        fn = item.get("function", item)
        args = fn.get("arguments") or {}
        if not isinstance(args, str):
            args = j(args)
        normalized.append({
            "id": item.get("id", ""),
            "type": item.get("type", "function"),
            "function": {
                "name": fn.get("name", ""),
                "arguments": args,
            },
        })
    return normalized


def references_from_tool_events(events: list[dict]) -> list[dict]:
    refs: list[dict] = []
    for event in events:
        if event.get("type") != "tool_result":
            continue
        name = event.get("name", "tool") or ""
        result = event.get("result", {}) or {}
        inner = result
        if isinstance(inner, dict) and "data" in inner:
            inner = inner["data"]
        results_list = []
        if isinstance(inner, dict):
            results_list = inner.get("results", [])
        elif isinstance(inner, list):
            results_list = inner
        if results_list:
            for r_item in results_list:
                doc_name = r_item.get("document_name") or r_item.get("filename", "")
                page = r_item.get("page")
                excerpt = (r_item.get("text") or r_item.get("page_fusion", "") or "")[:240]
                title_parts = []
                if doc_name:
                    title_parts.append(doc_name)
                if page is not None:
                    title_parts.append(f"第{page}页")
                title = " ".join(title_parts) if title_parts else "知识库"
                refs.append({
                    "type": "knowledge",
                    "title": title,
                    "source": doc_name or "知识库",
                    "excerpt": excerpt,
                })
        else:
            refs.append({
                "type": "tool",
                "title": name,
                "source": name,
                "excerpt": j(result)[:240],
            })
    return refs
