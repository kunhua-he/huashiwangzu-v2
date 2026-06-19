"""Edit operations - 1:1 from old 表格/编辑.php"""
import json
from typing import Any

from backend.state.manager import cell_set_text, cell_get_style_ref, cell_set_style_val
from backend.tool.formula import calculate_formula


class EditOperations:

    @staticmethod
    async def execute(
        method: str, state: dict, state_key: str,
        addrs: list[str], params: dict
    ) -> dict:
        """Execute edit operation"""
        operations = {
            'input': EditOperations._input,
            'batch_fill': EditOperations._batch_fill,
            'clear': EditOperations._clear,
            'hyperlink': EditOperations._hyperlink,
            'format': EditOperations._format,
            'formula': EditOperations._formula,
        }
        func = operations.get(method)
        if not func:
            return {'code': 1, 'msg': f'Unknown edit method: {method}'}
        return await func(state, state_key, addrs, params)

    @staticmethod
    async def _input(state: dict, state_key: str, addrs: list[str], params: dict) -> dict:
        affected = addrs
        for addr in addrs:
            cell_set_text(state, addr, params.get('value', ''))
        return {'code': 0, 'affected_addrs': affected, 'affected_addr': affected[0] if affected else ''}

    @staticmethod
    async def _batch_fill(state: dict, state_key: str, addrs: list[str], params: dict) -> dict:
        fill_list = params.get('fill_list', [])
        affected = []
        for item in fill_list:
            addr = item.get('address', '')
            value = item.get('value', '')
            if not addr:
                continue
            cell_set_text(state, addr, str(value))
            affected.append(addr)
        return {'code': 0, 'affected_addrs': affected, 'affected_addr': affected[0] if affected else ''}

    @staticmethod
    async def _clear(state: dict, state_key: str, addrs: list[str], params: dict) -> dict:
        clear_type = params.get('type', 'all')
        for addr in addrs:
            if clear_type in ('all', 'content'):
                cell_set_text(state, addr, '')
            if clear_type in ('all', 'format'):
                state.get('styles', {}).pop(addr, None)
        return {'code': 0, 'affected_addrs': addrs}

    @staticmethod
    async def _hyperlink(state: dict, state_key: str, addrs: list[str], params: dict) -> dict:
        url = params.get('link', '')
        for addr in addrs:
            style = cell_get_style_ref(state, addr)
            style['link'] = url
        return {'code': 0, 'affected_addrs': addrs}

    @staticmethod
    async def _format(state: dict, state_key: str, addrs: list[str], params: dict) -> dict:
        fmt = params.get('format', 'general')
        for addr in addrs:
            cell_set_style_val(state, addr, 'numberFormat', fmt)
        return {'code': 0, 'affected_addrs': addrs}

    @staticmethod
    async def _formula(state: dict, state_key: str, addrs: list[str], params: dict) -> dict:
        formula_text = params.get('formula', '')
        result = calculate_formula(formula_text, state.get('cells', {}))
        return {'code': 0, 'result': result}
