"""Address utility - 1:1 from old 工具/地址工具.php

Handles Excel A1-style address parsing and conversion.
"""
import re


def parse_address(address: str) -> dict:
    """Parse 'A1' -> {'r': 1, 'c': 0} (1-based row, 0-based col)"""
    m = re.match(r'^([A-Z]+)(\d+)$', address.upper())
    if not m:
        return {'r': 0, 'c': 0}
    col_str = m.group(1)
    row = int(m.group(2))
    ci = 0
    for ch in col_str:
        ci = ci * 26 + (ord(ch) - 64)
    return {'r': row, 'c': ci - 1}


def rc_to_address(r: int, c: int) -> str:
    """Convert (row=1, col=0) -> 'A1' (1-based row, 0-based col)"""
    t = c + 1
    s = ''
    while t > 0:
        t -= 1
        s = chr(65 + (t % 26)) + s
        t //= 26
    return f'{s}{r}'


def col_letter(n: int) -> str:
    """0 -> A, 25 -> Z, 26 -> AA"""
    return rc_to_address(1, n).rstrip('0123456789')


def parse_range(range_str: str) -> tuple[dict, dict]:
    """Parse 'A1:B3' -> ({r:1,c:0}, {r:3,c:1})"""
    parts = range_str.split(':')
    if len(parts) != 2:
        return (parse_address(range_str), parse_address(range_str))
    return (parse_address(parts[0]), parse_address(parts[1]))


def expand_range(range_str: str) -> list[str]:
    """Parse 'A1:C3' into list of all cell addresses in range"""
    tl, br = parse_range(range_str)
    cells = []
    for r in range(tl['r'], br['r'] + 1):
        for c in range(tl['c'], br['c'] + 1):
            cells.append(rc_to_address(r, c))
    return cells


def col_letter_to_index(col: str) -> int:
    """'A' -> 0, 'AA' -> 26"""
    ci = 0
    for ch in col.upper():
        ci = ci * 26 + (ord(ch) - 64)
    return ci - 1
