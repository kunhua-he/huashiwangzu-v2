"""Style parsing - 1:1 from old 解析_样式表.php"""
import xml.etree.ElementTree as ET
import zipfile
from typing import Any

from .color_parser import parse_color_node

SPREAD_NS = 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'


def read_styles(zf: zipfile.ZipFile, theme_colors: dict[int, str]) -> tuple:
    """Read styles from xl/styles.xml - returns (fonts, fills, borders, numFmts, cellXf, alignments)"""
    fonts: list[dict[str, Any]] = []
    fills: list[dict[str, Any]] = []
    borders: list[dict[str, Any]] = []
    num_fmts: dict[int, str] = {}
    cell_xf: list[dict[str, Any]] = []
    alignments: list[dict[str, Any]] = []

    try:
        content = zf.read('xl/styles.xml')
    except KeyError:
        return fonts, fills, borders, num_fmts, cell_xf, alignments

    root = ET.fromstring(content)

    # Number formats
    for nf in root.findall(f'.//{{{SPREAD_NS}}}numFmts/{{{SPREAD_NS}}}numFmt'):
        nf_id = int(nf.get('numFmtId', '0'))
        fmt_code = nf.get('formatCode', '')
        num_fmts[nf_id] = fmt_code

    # Fonts
    for font in root.findall(f'.//{{{SPREAD_NS}}}fonts/{{{SPREAD_NS}}}font'):
        f: dict[str, Any] = {}
        sz = font.find(f'{{{SPREAD_NS}}}sz')
        if sz is not None:
            f['size'] = float(sz.get('val', '11'))
        name = font.find(f'{{{SPREAD_NS}}}name')
        if name is not None:
            f['name'] = name.get('val', '宋体')
        color = font.find(f'{{{SPREAD_NS}}}color')
        if color is not None:
            f['color'] = parse_color_node(color, theme_colors)
        b = font.find(f'{{{SPREAD_NS}}}b')
        if b is not None:
            f['bold'] = True
        i = font.find(f'{{{SPREAD_NS}}}i')
        if i is not None:
            f['italic'] = True
        u = font.find(f'{{{SPREAD_NS}}}u')
        if u is not None:
            f['underline'] = True
        strike = font.find(f'{{{SPREAD_NS}}}strike')
        if strike is not None:
            f['strikethrough'] = True
        fonts.append(f)

    # Fills
    for fill in root.findall(f'.//{{{SPREAD_NS}}}fills/{{{SPREAD_NS}}}fill'):
        fl: dict[str, Any] = {}
        pf = fill.find(f'{{{SPREAD_NS}}}patternFill')
        if pf is not None:
            fl['pattern'] = pf.get('patternType', 'none')
            fg = pf.find(f'{{{SPREAD_NS}}}fgColor')
            if fg is not None:
                c = parse_color_node(fg, theme_colors)
                if c:
                    fl['fgColor'] = c
            bg = pf.find(f'{{{SPREAD_NS}}}bgColor')
            if bg is not None:
                c = parse_color_node(bg, theme_colors)
                if c:
                    fl['bgColor'] = c
        fills.append(fl)

    # Borders
    for border in root.findall(f'.//{{{SPREAD_NS}}}borders/{{{SPREAD_NS}}}border'):
        bd: dict[str, Any] = {}
        for side_name in ['left', 'right', 'top', 'bottom']:
            side = border.find(f'{{{SPREAD_NS}}}{side_name}')
            if side is not None:
                style = side.get('style')
                if style:
                    bd[side_name] = {'style': style}
                    sc = side.find(f'{{{SPREAD_NS}}}color')
                    if sc is not None:
                        c = parse_color_node(sc, theme_colors)
                        if c:
                            bd[side_name]['color'] = c
        borders.append(bd)

    # Cell style formats
    for xf in root.findall(f'.//{{{SPREAD_NS}}}cellXfs/{{{SPREAD_NS}}}xf'):
        x: dict[str, Any] = {}
        x['fontId'] = int(xf.get('fontId', '0'))
        x['fillId'] = int(xf.get('fillId', '0'))
        x['borderId'] = int(xf.get('borderId', '0'))
        x['numFmtId'] = int(xf.get('numFmtId', '0'))
        x['applyFont'] = xf.get('applyFont', '0') == '1'
        x['applyFill'] = xf.get('applyFill', '0') == '1'
        x['applyBorder'] = xf.get('applyBorder', '0') == '1'
        x['applyNumberFormat'] = xf.get('applyNumberFormat', '0') == '1'
        x['applyAlignment'] = xf.get('applyAlignment', '0') == '1'
        al = xf.find(f'{{{SPREAD_NS}}}alignment')
        if al is not None:
            al_info: dict[str, Any] = {}
            h = al.get('horizontal')
            if h:
                al_info['horizontal'] = h
            v = al.get('vertical')
            if v:
                al_info['vertical'] = v
            wrap = al.get('wrapText')
            if wrap:
                al_info['wrapText'] = wrap == '1'
            alignments.append(al_info)
            x['alignment'] = len(alignments) - 1
        cell_xf.append(x)

    return fonts, fills, borders, num_fmts, cell_xf, alignments
