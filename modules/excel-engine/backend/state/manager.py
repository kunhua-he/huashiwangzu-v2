"""State manager - 1:1 from old 表格/状态.php + traits

Central state management with DB persistence, history, snapshot, styles.
"""
import os
from typing import Any

from backend.tool.config import DEFAULT_TOTAL_ROWS, DEFAULT_TOTAL_COLS

TEMP_DIR: str = ''


def init_state(temp_dir: str):
    global TEMP_DIR
    TEMP_DIR = temp_dir
    os.makedirs(temp_dir, exist_ok=True)


def cell_get_text(state: dict, addr: str) -> str:
    return state.get('cells', {}).get(addr, '')


def cell_set_text(state: dict, addr: str, value: str):
    cells = state.setdefault('cells', {})
    if value == '':
        cells.pop(addr, None)
    else:
        cells[addr] = value


def cell_get_style_ref(state: dict, addr: str) -> dict:
    styles = state.setdefault('styles', {})
    if addr not in styles:
        styles[addr] = {}
    return styles[addr]


def cell_set_style_val(state: dict, addr: str, key: str, value: Any):
    styles = state.setdefault('styles', {})
    if addr not in styles:
        styles[addr] = {}
    styles[addr][key] = value


def cell_get_data(state: dict, addr: str) -> dict:
    return {
        'text': state.get('cells', {}).get(addr, ''),
        'style': state.get('styles', {}).get(addr, {}),
    }


def parse_addresses(params: dict) -> list[str]:
    addrs = params.get('address_list', params.get('addrs', []))
    if isinstance(addrs, list) and len(addrs) > 0:
        return addrs
    addr = params.get('address', params.get('addr', ''))
    return [addr] if addr else []


def build_snapshot(state: dict) -> dict:
    return {
        'cells': state.get('cells', {}),
        'styles': state.get('styles', {}),
        'merges': state.get('merges', {}),
        'col_widths': state.get('col_widths', {}),
        'row_heights': state.get('row_heights', {}),
        'total_rows': state.get('total_rows', DEFAULT_TOTAL_ROWS),
        'total_cols': state.get('total_cols', DEFAULT_TOTAL_COLS),
    }


def empty_state() -> dict:
    """返回一个全新的空表格状态。"""
    return {
        'cells': {},
        'styles': {},
        'merges': {},
        'col_widths': {},
        'row_heights': {},
        'total_rows': DEFAULT_TOTAL_ROWS,
        'total_cols': DEFAULT_TOTAL_COLS,
    }
