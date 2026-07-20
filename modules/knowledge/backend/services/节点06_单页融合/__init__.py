# -*- coding: utf-8 -*-
"""节点⑥ 单页融合：文本层优先，LLM 降级为补充/兜底。

对外只暴露 fuse_document（及中文别名 融合文档）。
子文件禁止被外部直接 import。
"""

from .对外接口 import fuse_document, 融合文档

__all__ = ["fuse_document", "融合文档"]
