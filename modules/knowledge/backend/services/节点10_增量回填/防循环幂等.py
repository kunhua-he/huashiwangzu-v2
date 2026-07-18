# -*- coding: utf-8 -*-
"""防循环幂等（骨架 deferred）。

★ 强调：防 A 补 B、B 补 A 死循环。
设计要点（激活时实现）：
- 回填边带 directed + generation / content_hash
- 同一 (src_doc, tgt_doc, claim_hash) 只写一次
- 禁止反向立刻再触发同 claim
- 全局 depth 上限
"""
from __future__ import annotations

from typing import Any


def 是否允许回填(
    src_document_id: int,
    tgt_document_id: int,
    claim_hash: str,
    *,
    seen: set[tuple[int, int, str]] | None = None,
) -> dict[str, Any]:
    """骨架：仅接口形状，恒 deferred。"""
    _ = (src_document_id, tgt_document_id, claim_hash, seen)
    return {"status": "deferred", "allowed": False, "module": "防循环幂等"}
