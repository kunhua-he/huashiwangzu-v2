# -*- coding: utf-8 -*-
"""节点④ 图像描述 / OCR 分家（模块化包装）。

对外只暴露 描述图像。不改 raw_collection_service / pipeline_stages。
"""

from .对外接口 import 描述图像

__all__ = ["描述图像"]
