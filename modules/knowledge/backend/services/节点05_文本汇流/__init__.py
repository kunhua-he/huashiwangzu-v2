# -*- coding: utf-8 -*-
"""节点⑤ 文本汇流。

对外只暴露 汇流。只读 kb_raw_data，不写库、不烧模型。
"""
from .对外接口 import converge_text_layers, 汇流

__all__ = ["汇流", "converge_text_layers"]
