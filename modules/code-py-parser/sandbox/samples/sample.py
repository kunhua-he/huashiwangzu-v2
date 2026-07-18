"""示例 Python 模块：演示函数与类切块。"""

import math


def hello(name: str) -> str:
    """打招呼。"""
    return f"hello {name}"


class Greeter:
    """问候器。"""

    def greet(self) -> str:
        return hello("world")


# 尾部说明：用于检索的注释块
# 第二行注释
