"""Sheet data parser - 1:1 from old 解析_子表.php"""
import re
import xml.etree.ElementTree as ET
import zipfile
from typing import Any

SPREAD_NS = 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'


def _decode_ascii_escape(val: str) -> str:
    """Decode [ASCII:0x00XX] escape sequences"""
    def _replace(m):
        hex_val = m.group(1)
        return chr(int(hex_val, 16))
    return re.sub(r'\[ASCII:0x([0-9A-F]{4})\]', _replace, val)


def parse_sheet_data(
    zf: zipfile.ZipFile, sheet_file: str, shared_strings: list[str],
    fonts: list, fills: list, borders: list,
    num_fmts: dict[int, str], cell_xf: list, alignments: list
) -> dict[str, Any] | None:
    """Parse a single sheet's XML data - 1:1 from old _解析子表数据"""
    try:
        content = zf.read(f'xl/{sheet_file}')
    except KeyError:
        return None

    root = ET.fromstring(content)
    cells: dict[str, str] = {}
    frontend_styles: dict[str, dict[str, Any]] = {}
    merges: dict[str, dict[str, Any]] = {}
    col_widths: dict[str, int] = {}
    row_heights: dict[str, int] = {}
    max_row = 0
    max_col = 0

    # Column widths
    for col in root.findall(f'.//{{{SPREAD_NS}}}cols/{{{SPREAD_NS}}}col'):
        col_min = int(col.get('min', '1'))
        col_max = int(col.get('max', '1'))
        width = float(col.get('width', '10'))
        custom_width = col.get('customWidth', '0')
        if custom_width == '1':
            px = int(width * 7)
            for ci in range(col_min, col_max + 1):
                letter = ''
                t = ci
                while t > 0:
                    t -= 1
                    letter = chr(65 + (t % 26)) + letter
                    t //= 26
                col_widths[letter] = px

    # Row heights
    for row in root.findall(f'.//{{{SPREAD_NS}}}sheetData/{{{SPREAD_NS}}}row'):
        r = int(row.get('r', '1'))
        ht = row.get('ht')
        custom_h = row.get('customHeight', '0')
        if ht and custom_h == '1':
            row_heights[str(r)] = int(float(ht) * 4)
        if r > max_row:
            max_row = r

        for c in row.findall(f'{{{SPREAD_NS}}}c'):
            ref = c.get('r', '')
            cell_type = c.get('t', '')
            style_id = c.get('s')

            # Parse column from ref like 'A1'
            m = re.match(r'([A-Z]+)(\d+)', ref)
            if not m:
                continue
            col_str = m.group(1)
            ci = 0
            for ch in col_str:
                ci = ci * 26 + (ord(ch) - 64)
            ci -= 1
            if ci > max_col:
                max_col = ci

            # Cell value
            val_elem = c.find(f'{{{SPREAD_NS}}}v')
            raw_val = val_elem.text if val_elem is not None else ''
            if cell_type == 's' and raw_val:
                si = int(raw_val)
                raw_val = shared_strings[si] if si < len(shared_strings) else raw_val
            elif cell_type == 'inlineStr':
                t_elem = c.find(f'.//{{{SPREAD_NS}}}t')
                raw_val = t_elem.text if t_elem is not None else ''
            elif cell_type == 'str':
                raw_val = raw_val
            elif cell_type == 'e':
                raw_val = raw_val
            elif raw_val:
                raw_val = raw_val

            # Apply ASCII escape decode
            if '[ASCII:' in str(raw_val):
                raw_val = _decode_ascii_escape(str(raw_val))

            cells[ref] = str(raw_val) if raw_val else ''

            # Style
            if style_id is not None and int(style_id) < len(cell_xf):
                xf = cell_xf[int(style_id)]
                style_info: dict[str, Any] = {}

                if xf.get('applyFont') and xf['fontId'] < len(fonts):
                    f = fonts[xf['fontId']]
                    if 'bold' in f:
                        style_info['bold'] = True
                    if 'italic' in f:
                        style_info['italic'] = True
                    if 'underline' in f:
                        style_info['underline'] = True
                    if 'strikethrough' in f:
                        style_info['strikethrough'] = True
                    if 'size' in f:
                        style_info['fontSize'] = f['size']
                    if 'name' in f:
                        style_info['fontName'] = f['name']
                    if 'color' in f:
                        style_info['color'] = f['color']

                if xf.get('applyFill') and xf['fillId'] < len(fills):
                    fl = fills[xf['fillId']]
                    if 'fgColor' in fl:
                        style_info['fillColor'] = fl['fgColor']

                if xf.get('applyAlignment') and 'alignment' in xf:
                    al_idx = xf['alignment']
                    if al_idx < len(alignments):
                        al = alignments[al_idx]
                        if 'horizontal' in al:
                            h_map = {'left': '左', 'center': '居中', 'right': '右'}
                            style_info['align'] = h_map.get(al['horizontal'], '左')
                        if 'wrapText' in al and al['wrapText']:
                            style_info['wrapText'] = True

                if style_info:
                    frontend_styles[ref] = style_info

    # Merged cells
    for mc in root.findall(f'.//{{{SPREAD_NS}}}mergeCells/{{{SPREAD_NS}}}mergeCell'):
        ref = mc.get('ref', '')
        if ref and ':' in ref:
            parts = ref.split(':')
            tl = parts[0]
            br = parts[1]
            m_tl = re.match(r'([A-Z]+)(\d+)', tl)
            m_br = re.match(r'([A-Z]+)(\d+)', br)
            if m_tl and m_br:
                row_diff = int(m_br.group(2)) - int(m_tl.group(2)) + 1
                ci1 = 0
                for ch in m_tl.group(1):
                    ci1 = ci1 * 26 + (ord(ch) - 64)
                ci2 = 0
                for ch in m_br.group(1):
                    ci2 = ci2 * 26 + (ord(ch) - 64)
                col_diff = ci2 - ci1 + 1
                merges[ref] = {
                    'topLeft': tl, 'rows': row_diff, 'cols': col_diff
                }
                if int(m_br.group(2)) > max_row:
                    max_row = int(m_br.group(2))
                if ci2 > max_col:
                    max_col = ci2

    return {
        'cells': cells,
        'styles': frontend_styles,
        'merges': merges,
        'col_widths': col_widths,
        'row_heights': row_heights,
        'total_rows': max(max_row, 1),
        'total_cols': max(max_col, 10),
    }
