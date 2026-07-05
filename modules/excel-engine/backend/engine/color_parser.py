"""Color parsing - 1:1 from old 解析_颜色.php"""
import xml.etree.ElementTree as ET
import zipfile

CLR_NS = 'http://schemas.openxmlformats.org/drawingml/2006/main'
SPREAD_NS = 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'

INDEXED_COLORS = {
    0: '000000', 1: 'FFFFFF', 2: 'FF0000', 3: '00FF00', 4: '0000FF',
    5: 'FFFF00', 6: 'FF00FF', 7: '00FFFF', 8: '000000', 9: 'FFFFFF',
    10: 'FF0000', 11: '00FF00', 12: '0000FF', 13: 'FFFF00', 14: 'FF00FF',
    15: '00FFFF', 16: '800000', 17: '008000', 18: '000080', 19: '808000',
    20: '800080', 21: '008080', 22: 'C0C0C0', 23: '808080',
}


def apply_tint(rgb_hex: str, tint: float) -> str:
    """Apply tint to RGB color - 1:1 from old _应用Tint"""
    r = int(rgb_hex[0:2], 16)
    g = int(rgb_hex[2:4], 16)
    b = int(rgb_hex[4:6], 16)
    if tint < 0:
        r = round(r * (1 + tint))
        g = round(g * (1 + tint))
        b = round(b * (1 + tint))
    else:
        r = round(r + (255 - r) * tint)
        g = round(g + (255 - g) * tint)
        b = round(b + (255 - b) * tint)
    return f'#{max(0, min(255, r)):02X}{max(0, min(255, g)):02X}{max(0, min(255, b)):02X}'


def parse_color_node(color_elem: ET.Element | None, theme_colors: dict[int, str]) -> str | None:
    """Parse color XML node - 1:1 from old _解析颜色节点"""
    if color_elem is None:
        return None
    rgb = color_elem.get('rgb', '')
    if rgb and len(rgb) >= 8:
        return '#' + rgb[-6:]
    theme = color_elem.get('theme')
    if theme is not None and int(theme) in theme_colors:
        base_color = theme_colors[int(theme)]
        tint_str = color_elem.get('tint')
        if tint_str:
            base_color = apply_tint(base_color, float(tint_str)).lstrip('#')
        return '#' + base_color
    indexed = color_elem.get('indexed')
    if indexed is not None:
        idx = int(indexed)
        if idx in INDEXED_COLORS:
            return '#' + INDEXED_COLORS[idx]
    return None


def read_theme_colors(zf: zipfile.ZipFile) -> dict[int, str]:
    """Read theme colors from xl/theme/theme1.xml - 1:1 from old"""
    theme_colors: dict[int, str] = {}
    for theme_path in ['xl/theme/theme1.xml', 'xl/theme/theme2.xml']:
        try:
            content = zf.read(theme_path)
        except KeyError:
            continue
        root = ET.fromstring(content)
        clr_scheme = root.find(f'.//{{{CLR_NS}}}clrScheme')
        if clr_scheme is None:
            continue
        color_map = {
            'lt1': 0, 'dk1': 1, 'lt2': 2, 'dk2': 3,
            'accent1': 4, 'accent2': 5, 'accent3': 6, 'accent4': 7,
            'accent5': 8, 'accent6': 9, 'hlink': 10, 'folHlink': 11,
        }
        for name, idx in color_map.items():
            tag = f'{{{CLR_NS}}}{name}'
            node = clr_scheme.find(tag)
            if node is None:
                continue
            srgb = node.find(f'.//{{{CLR_NS}}}srgbClr')
            if srgb is not None:
                theme_colors[idx] = srgb.get('val', '')
                continue
            sys_clr = node.find(f'.//{{{CLR_NS}}}sysClr')
            if sys_clr is not None:
                theme_colors[idx] = sys_clr.get('lastClr', 'FFFFFF')
        if theme_colors:
            break
    return theme_colors
