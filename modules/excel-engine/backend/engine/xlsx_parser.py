"""XLSX parser - 1:1 from old 引擎/xlsx解析.php + sub-parsers."""
import zipfile
from typing import Any

from ..tool.config import DEFAULT_TOTAL_COLS, DEFAULT_TOTAL_ROWS
from .color_parser import read_theme_colors
from .shared_strings import read_shared_strings
from .sheet_parser import parse_sheet_data
from .style_parser import read_styles
from .workbook_parser import read_workbook_list


def parse_xlsx(path: str, filename: str = '', target_sheet: str = '') -> dict[str, Any]:
    try:
        zf = zipfile.ZipFile(path, 'r')
    except Exception as e:
        return {'code': 1, 'msg': f'Unable to open xlsx: {e}'}

    try:
        theme_colors = read_theme_colors(zf)
        shared_strings = read_shared_strings(zf)
        fonts, fills, borders, num_fmts, cell_xf, alignments = read_styles(zf, theme_colors)
        all_sheets, sheet_map, rid_map = read_workbook_list(zf)

        all_sheet_data = {}
        for sheet_name in all_sheets:
            rid = sheet_map.get(sheet_name, '')
            sheet_file = rid_map.get(rid, '')
            if not sheet_file:
                continue
            data = parse_sheet_data(zf, sheet_file, shared_strings, fonts, fills, borders, num_fmts, cell_xf, alignments)
            if data:
                all_sheet_data[sheet_name] = data

        zf.close()

        if not all_sheet_data:
            all_sheet_data['Sheet1'] = {
                'cells': {}, 'styles': {}, 'merges': [],
                'col_widths': {}, 'row_heights': {},
                'total_rows': DEFAULT_TOTAL_ROWS, 'total_cols': DEFAULT_TOTAL_COLS,
            }
            all_sheets = ['Sheet1']

        if target_sheet:
            if target_sheet in all_sheet_data:
                sd = all_sheet_data[target_sheet]
                return {'code': 0, 'msg': 'OK', 'cells': sd['cells'], 'styles': sd['styles'],
                        'merges': sd['merges'], 'col_widths': sd['col_widths'],
                        'row_heights': sd['row_heights'], 'total_rows': sd['total_rows'],
                        'total_cols': sd['total_cols'], 'filename': filename,
                        'all_sheets': all_sheets, 'sheet_set': all_sheet_data}
            return {'code': 1, 'msg': f'Sheet not found: {target_sheet}'}

        return {'code': 0, 'msg': 'OK', 'all_sheets': all_sheets, 'sheet_set': all_sheet_data, 'filename': filename}

    except Exception as e:
        zf.close()
        return {'code': 1, 'msg': f'Parse error: {e}'}
