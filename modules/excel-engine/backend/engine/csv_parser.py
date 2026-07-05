"""CSV parser - 1:1 from old 引擎/csv解析.php"""
import csv
import io
from typing import Any

from ..tool.config import DEFAULT_TOTAL_COLS, DEFAULT_TOTAL_ROWS


def parse_csv(path: str, filename: str = '') -> dict[str, Any]:
    """Parse CSV file into state structure"""
    try:
        with open(path, 'rb') as f:
            raw = f.read()
    except Exception as e:
        return {'code': 1, 'msg': f'无法读取文件: {e}'}

    try:
        content = raw.decode('utf-8-sig')
    except UnicodeDecodeError:
        content = raw.decode('gbk', errors='replace')

    reader = csv.reader(io.StringIO(content))
    cells: dict[str, str] = {}
    max_col = 0
    for row_idx, row in enumerate(reader):
        r = row_idx + 1
        for col_idx, val in enumerate(row):
            addr = ''
            t = col_idx + 1
            while t > 0:
                t -= 1
                addr = chr(65 + (t % 26)) + addr
                t //= 26
            addr = f'{addr}{r}'
            cells[addr] = val.strip()
            if col_idx > max_col:
                max_col = col_idx

    total_rows = max(len(cells.keys()), DEFAULT_TOTAL_ROWS)
    total_cols = max(max_col + 1, DEFAULT_TOTAL_COLS)

    return {
        'code': 0, 'msg': '导入完成',
        'cells': cells,
        'styles': {},
        'merges': {},
        'col_widths': {},
        'row_heights': {},
        'total_rows': total_rows,
        'total_cols': total_cols,
        'filename': filename,
        'all_sheets': ['Sheet1'],
        'sheet_set': {
            'Sheet1': {
                'cells': cells, 'styles': {}, 'merges': {},
                'col_widths': {}, 'row_heights': {},
                'total_rows': total_rows, 'total_cols': total_cols,
            }
        },
    }
