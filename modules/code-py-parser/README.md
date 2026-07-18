# code-py-parser — Python Code Parser

本解析器：解析 Python 代码文件，按模块 docstring / def / class 切成统一 content-ir blocks。

切块规则：`切块规则.json`

## 对外能力

| 能力 | 说明 |
|------|------|
| `parse` | Parse Python files into semantic code blocks |
