"""Machine-readable release gate response helpers."""
import json
from typing import Any


def extract_prefixed_json(output: str, prefix: str) -> dict[str, Any] | None:
    for line in reversed(output.splitlines()):
        text = line.strip()
        if not text.startswith(prefix):
            continue
        try:
            data = json.loads(text[len(prefix):].strip())
        except json.JSONDecodeError:
            return None
        return data if isinstance(data, dict) else None
    return None


def tail_text(text: str, limit: int = 20000) -> str:
    if len(text) <= limit:
        return text
    return text[-limit:]


def build_release_gate_response(
    output: str,
    returncode: int,
    skip_ui: bool,
    duration_seconds: float,
) -> dict[str, Any]:
    summary = extract_prefixed_json(output, "RELEASE_GATE_JSON:")
    verdict = summary.get("verdict") if summary else ("PASS" if returncode == 0 else "BLOCKER")
    if not isinstance(verdict, str) or not verdict:
        verdict = "PASS" if returncode == 0 else "BLOCKER"
    clean_pass = returncode == 0 and verdict == "PASS"
    release_safe = returncode == 0 and verdict in {"PASS", "PASS_WITH_DEBT"}
    return {
        "success": clean_pass,
        "clean_pass": clean_pass,
        "release_safe": release_safe,
        "has_debt": verdict == "PASS_WITH_DEBT",
        "verdict": verdict,
        "returncode": returncode,
        "skip_ui": skip_ui,
        "duration_seconds": round(duration_seconds, 3),
        "summary": summary,
        "output": output,
        "output_tail": tail_text(output, 20000),
    }
