# -*- coding: utf-8 -*-
"""中文模块名动态加载。

规则：静态 import 不能写中文文件名，统一走 importlib。
"""
from __future__ import annotations

import importlib
import sys
from types import ModuleType
from typing import Any


def 加载本包模块(模块名: str) -> ModuleType:
    """加载当前包下中文模块，如 分词 / 库存落盘 / 对外接口。"""
    包名 = __package__ or "modules.knowledge.backend.services.节点07A_主体枚举"
    全名 = f"{包名}.{模块名}"
    if 全名 in sys.modules:
        return sys.modules[全名]
    return importlib.import_module(全名)


def 取属性(模块名: str, *属性名: str) -> Any:
    """加载模块并取一个或多个属性；单属性直接返回，多属性返回元组。"""
    模 = 加载本包模块(模块名)
    if len(属性名) == 1:
        return getattr(模, 属性名[0])
    return tuple(getattr(模, 名) for 名 in 属性名)
