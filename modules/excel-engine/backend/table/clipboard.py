"""Clipboard operations - 1:1 from old 表格/剪贴板.php"""
from typing import Any
from backend.state.manager import cell_get_text, cell_set_text, cell_get_style_ref
from backend.tool.address import parse_address, rc_to_address


class ClipboardOperations:

    @staticmethod
    async def execute(method: str, state: dict, state_key: str, addrs: list[str], params: dict) -> dict:
        if method == 'copy':
            return ClipboardOperations._copy(state, addrs)
        elif method == 'paste':
            return ClipboardOperations._paste(state, addrs, params)
        return {'code': 1, 'msg': f'Unknown clipboard method: {method}'}

    @staticmethod
    def _copy(state: dict, addrs: list[str]) -> dict:
        clipboard_data = {}
        for addr in addrs:
            clipboard_data[addr] = {
                'text': cell_get_text(state, addr),
                'style': state.get('styles', {}).get(addr, {}),
            }
        state['_clipboard'] = clipboard_data
        state['_clipboard_range'] = addrs
        return {'code': 0}

    @staticmethod
    def _paste(state: dict, addrs: list[str], params: dict) -> dict:
        paste_data = params.get('data', [])
        start_addr = addrs[0] if addrs else 'A1'
        start_rc = parse_address(start_addr)

        affected = []
        clipboard_style = state.get('_clipboard', {})
        clipboard_keys = list(clipboard_style.keys())
        clip_styles = [clipboard_style[k].get('style', {}) for k in clipboard_keys]
        clip_col_count = len(clipboard_keys) if clipboard_keys else 1

        for row_idx, row in enumerate(paste_data):
            for col_idx, value in enumerate(row):
                addr = rc_to_address(start_rc['r'] + row_idx, start_rc['c'] + col_idx)
                cell_set_text(state, addr, str(value))
                style_idx = row_idx * clip_col_count + col_idx
                if style_idx < len(clip_styles) and clip_styles[style_idx]:
                    state.setdefault('styles', {})[addr] = clip_styles[style_idx]
                affected.append(addr)

        return {'code': 0, 'affected_addrs': affected, 'affected_addr': affected[0] if affected else ''}
