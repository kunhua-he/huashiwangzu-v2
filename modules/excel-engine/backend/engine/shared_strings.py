"""Shared strings parser - 1:1 from old 解析_共享字符串.php"""
import zipfile
import xml.etree.ElementTree as ET

SPREAD_NS = 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'


def read_shared_strings(zf: zipfile.ZipFile) -> list[str]:
    """Read shared strings from xl/sharedStrings.xml"""
    try:
        content = zf.read('xl/sharedStrings.xml')
    except KeyError:
        return []
    root = ET.fromstring(content)
    strings = []
    for si in root.findall(f'.//{{{SPREAD_NS}}}si'):
        text_parts = []
        for t in si.findall(f'.//{{{SPREAD_NS}}}t'):
            if t.text:
                text_parts.append(t.text)
        strings.append(''.join(text_parts))
    return strings
