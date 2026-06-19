"""Formula calculation engine - 1:1 from old 工具/公式.php

Supports: SUM, AVERAGE, COUNT, MAX, MIN and basic arithmetic.
"""
import re
from .address import parse_address, rc_to_address


def calculate_formula(expression: str, cells: dict[str, str]) -> str:
    """Evaluate an Excel formula expression."""
    if not expression.startswith('='):
        return expression
    body = expression[1:].strip()
    m = re.match(r'^(SUM|AVERAGE|COUNT|MAX|MIN)\((.+)\)$', body, re.IGNORECASE)
    if m:
        func_name = m.group(1).upper()
        args_str = m.group(2)
        return _execute_function(func_name, args_str, cells)
    result = _safe_arithmetic(body, cells)
    if result is not None and isinstance(result, (int, float)):
        return str(result)
    return '#VALUE!'


def _execute_function(name: str, args_str: str, cells: dict[str, str]) -> str:
    numbers = _get_number_list(args_str, cells)
    if numbers is None:
        return '#VALUE!'
    if name == 'SUM':
        return str(sum(numbers))
    elif name == 'AVERAGE':
        return str(sum(numbers) / len(numbers)) if numbers else '#DIV/0!'
    elif name == 'COUNT':
        return str(len(numbers))
    elif name == 'MAX':
        return str(max(numbers)) if numbers else '#VALUE!'
    elif name == 'MIN':
        return str(min(numbers)) if numbers else '#VALUE!'
    return '#NAME?'


def _get_number_list(args_str: str, cells: dict[str, str]) -> list[float] | None:
    parts = [p.strip() for p in args_str.split(',')]
    numbers = []
    for part in parts:
        if ':' in part:
            tl, br = part.split(':')
            tl_p = parse_address(tl)
            br_p = parse_address(br)
            for r in range(tl_p['r'], br_p['r'] + 1):
                for c in range(tl_p['c'], br_p['c'] + 1):
                    addr = rc_to_address(r, c)
                    val = cells.get(addr, '0')
                    try:
                        numbers.append(float(val))
                    except (ValueError, TypeError):
                        numbers.append(0.0)
        else:
            val = cells.get(part, '0')
            try:
                numbers.append(float(val))
            except (ValueError, TypeError):
                numbers.append(0.0)
    return numbers


def _safe_arithmetic(expression: str, cells: dict[str, str]) -> float | int | None:
    def _replace_cell(m):
        addr = m.group(0)
        val = cells.get(addr, '0')
        try:
            float(val)
            return val
        except ValueError:
            return '0'
    expr = re.sub(r'[A-Z]+\d+', _replace_cell, expression)
    expr = re.sub(r'\s+', '', expr)
    if not re.match(r'^[0-9+\-*/().]+$', expr):
        return None
    try:
        return eval(expr)
    except Exception:
        return None
