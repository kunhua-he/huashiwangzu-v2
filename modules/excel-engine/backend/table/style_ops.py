"""Style operations - 1:1 from old 表格/样式.php"""
from typing import Any
from backend.state.manager import cell_get_style_ref


class StyleOperations:

    @staticmethod
    async def execute(method: str, state: dict, state_key: str, addrs: list[str], params: dict) -> dict:
        operations = {
            'bold': lambda: StyleOperations._toggle_style(state, addrs, 'bold'),
            'italic': lambda: StyleOperations._toggle_style(state, addrs, 'italic'),
            'underline': lambda: StyleOperations._toggle_style(state, addrs, 'underline'),
            'strikethrough': lambda: StyleOperations._toggle_style(state, addrs, 'strikethrough'),
            'align_left': lambda: StyleOperations._set_align(state, addrs, '左'),
            'align_center': lambda: StyleOperations._set_align(state, addrs, '居中'),
            'align_right': lambda: StyleOperations._set_align(state, addrs, '右'),
            'font': lambda: StyleOperations._set_font(state, addrs, params),
            'font_size': lambda: StyleOperations._set_font_size(state, addrs, params),
            'fill_color': lambda: StyleOperations._set_color(state, addrs, params, 'fillColor'),
            'font_color': lambda: StyleOperations._set_color(state, addrs, params, 'color'),
            'wrap_text': lambda: StyleOperations._wrap_text(state, addrs),
            'border': lambda: StyleOperations._border(state, addrs, params),
        }
        func = operations.get(method)
        if not func:
            return {'code': 1, 'msg': f'Unknown style method: {method}'}
        return await func()

    @staticmethod
    async def _toggle_style(state: dict, addrs: list[str], key: str) -> dict:
        for addr in addrs:
            style = cell_get_style_ref(state, addr)
            style[key] = not style.get(key, False)
        return {'code': 0, 'affected_addrs': addrs}

    @staticmethod
    async def _set_align(state: dict, addrs: list[str], align: str) -> dict:
        for addr in addrs:
            style = cell_get_style_ref(state, addr)
            style['align'] = align
        return {'code': 0, 'affected_addrs': addrs}

    @staticmethod
    async def _set_font(state: dict, addrs: list[str], params: dict) -> dict:
        font_name = params.get('value', '宋体')
        for addr in addrs:
            style = cell_get_style_ref(state, addr)
            style['fontName'] = font_name
        return {'code': 0, 'affected_addrs': addrs}

    @staticmethod
    async def _set_font_size(state: dict, addrs: list[str], params: dict) -> dict:
        size = float(params.get('value', 11))
        for addr in addrs:
            style = cell_get_style_ref(state, addr)
            style['fontSize'] = size
        return {'code': 0, 'affected_addrs': addrs}

    @staticmethod
    async def _set_color(state: dict, addrs: list[str], params: dict, key: str) -> dict:
        color = params.get('color', '#000000')
        for addr in addrs:
            style = cell_get_style_ref(state, addr)
            style[key] = color
        return {'code': 0, 'affected_addrs': addrs}

    @staticmethod
    async def _wrap_text(state: dict, addrs: list[str]) -> dict:
        for addr in addrs:
            style = cell_get_style_ref(state, addr)
            style['wrapText'] = not style.get('wrapText', False)
        return {'code': 0, 'affected_addrs': addrs}

    @staticmethod
    async def _border(state: dict, addrs: list[str], params: dict) -> dict:
        border_type = params.get('type', 'all')
        border_style = params.get('style', 'thin')
        for addr in addrs:
            style = cell_get_style_ref(state, addr)
            style['borderType'] = border_type
            style['borderStyle'] = border_style
        return {'code': 0, 'affected_addrs': addrs}
