# -*- coding: utf-8 -*-
"""节点07A 主体枚举：分词穷举落盘，不烧 LLM。"""
from __future__ import annotations

from ._动态加载 import 取属性

枚举, 枚举文档, enumerate_document = 取属性("对外接口", "枚举", "枚举文档", "enumerate_document")

__all__ = ["枚举", "枚举文档", "enumerate_document"]
