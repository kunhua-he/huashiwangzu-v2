"""Row/Column operations - 1:1 from old 表格/表格_行列操作.php"""
import re

from ..tool.address import rc_to_address


class RowColOperations:

    @staticmethod
    async def execute(method: str, state: dict, state_key: str, addrs: list[str], params: dict) -> dict:
        operations = {
            'delete_shift_right': lambda: RowColOperations._delete_shift_right(state, addrs),
            'delete_shift_up': lambda: RowColOperations._delete_shift_up(state, addrs),
            'delete_row': lambda: RowColOperations._delete_row(state, addrs),
            'delete_col': lambda: RowColOperations._delete_col(state, addrs),
            'insert_shift_right': lambda: RowColOperations._insert_shift_right(state, addrs),
            'insert_shift_down': lambda: RowColOperations._insert_shift_down(state, addrs),
            'insert_row_above': lambda: RowColOperations._insert_row_above(state, addrs),
            'insert_row_below': lambda: RowColOperations._insert_row_below(state, addrs),
            'insert_col_left': lambda: RowColOperations._insert_col_left(state, addrs),
            'insert_col_right': lambda: RowColOperations._insert_col_right(state, addrs),
            'merge': lambda: RowColOperations._merge(state, addrs, params),
            'unmerge': lambda: RowColOperations._unmerge(state, addrs),
            'sort': lambda: RowColOperations._sort(state, addrs, params),
        }
        func = operations.get(method)
        if not func:
            return {'code': 1, 'msg': f'Unknown table method: {method}'}
        return await func()

    @staticmethod
    def _parse_cell_ref(addr: str) -> tuple[int, int]:
        m = re.match(r'([A-Z]+)(\d+)', addr.upper())
        if not m:
            return (0, 0)
        col = 0
        for ch in m.group(1):
            col = col * 26 + (ord(ch) - 64)
        return (col - 1, int(m.group(2)))

    @staticmethod
    def _get_all_addrs(state: dict) -> list[str]:
        return list(state.get('cells', {}).keys())

    @staticmethod
    def _sorted_addrs(state: dict) -> list[tuple[int, int, str]]:
        result = []
        for addr in state.get('cells', {}):
            c, r = RowColOperations._parse_cell_ref(addr)
            result.append((r, c, addr))
        return sorted(result)

    @staticmethod
    def _bounds(addrs: list[str]) -> tuple[int, int, int, int] | None:
        parsed = [RowColOperations._parse_cell_ref(addr) for addr in addrs]
        parsed = [(col, row) for col, row in parsed if row > 0 and col >= 0]
        if not parsed:
            return None
        cols = [col for col, _ in parsed]
        rows = [row for _, row in parsed]
        return min(cols), max(cols), min(rows), max(rows)

    @staticmethod
    def _move_cell_maps(state: dict, transform) -> None:
        new_cells = {}
        new_styles = {}
        for addr, val in state.get('cells', {}).items():
            col, row = RowColOperations._parse_cell_ref(addr)
            new_addr = transform(col, row)
            if new_addr:
                new_cells[new_addr] = val
                if addr in state.get('styles', {}):
                    new_styles[new_addr] = state['styles'][addr]
        for addr, style in state.get('styles', {}).items():
            if addr in state.get('cells', {}):
                continue
            col, row = RowColOperations._parse_cell_ref(addr)
            new_addr = transform(col, row)
            if new_addr:
                new_styles[new_addr] = style
        state['cells'] = new_cells
        state['styles'] = new_styles

    @staticmethod
    def _drop_merges_touching_bounds(state: dict, min_col: int, max_col: int, min_row: int, max_row: int) -> None:
        kept = {}
        for merge_ref, info in state.get('merges', {}).items():
            tl = info.get('topLeft', '')
            col, row = RowColOperations._parse_cell_ref(tl)
            if min_col <= col <= max_col and min_row <= row <= max_row:
                continue
            kept[merge_ref] = info
        state['merges'] = kept

    @staticmethod
    async def _delete_row(state: dict, addrs: list[str]) -> dict:
        if not addrs:
            return {'code': 1, 'msg': 'No address'}
        _, row = RowColOperations._parse_cell_ref(addrs[0])
        total_rows = state.get('total_rows', 40)
        cells = state.get('cells', {})
        styles = state.get('styles', {})
        merges = state.get('merges', {})
        new_cells = {}
        new_styles = {}
        for addr, val in cells.items():
            c, r = RowColOperations._parse_cell_ref(addr)
            if r == row:
                continue
            new_r = r if r < row else r - 1
            new_addr = rc_to_address(new_r, c)
            new_cells[new_addr] = val
            if addr in styles:
                new_styles[new_addr] = styles[addr]
        state['cells'] = new_cells
        state['styles'] = new_styles
        state['total_rows'] = max(total_rows - 1, 1)
        # Shift merges
        state['merges'] = RowColOperations._shift_merges(merges, 'row', row, -1)
        return {'code': 0}

    @staticmethod
    async def _delete_col(state: dict, addrs: list[str]) -> dict:
        if not addrs:
            return {'code': 1, 'msg': 'No address'}
        col, _ = RowColOperations._parse_cell_ref(addrs[0])
        total_cols = state.get('total_cols', 10)
        cells = state.get('cells', {})
        styles = state.get('styles', {})
        merges = state.get('merges', {})
        new_cells = {}
        new_styles = {}
        for addr, val in cells.items():
            c, r = RowColOperations._parse_cell_ref(addr)
            if c == col:
                continue
            new_c = c if c < col else c - 1
            new_addr = rc_to_address(r, new_c)
            new_cells[new_addr] = val
            if addr in styles:
                new_styles[new_addr] = styles[addr]
        state['cells'] = new_cells
        state['styles'] = new_styles
        state['total_cols'] = max(total_cols - 1, 1)
        state['merges'] = RowColOperations._shift_merges(merges, 'col', col, -1)
        return {'code': 0}

    @staticmethod
    async def _insert_row_above(state: dict, addrs: list[str]) -> dict:
        if not addrs:
            return {'code': 1, 'msg': 'No address'}
        _, row = RowColOperations._parse_cell_ref(addrs[0])
        total_rows = state.get('total_rows', 40)
        cells = state.get('cells', {})
        styles = state.get('styles', {})
        merges = state.get('merges', {})
        new_cells = {}
        new_styles = {}
        for addr, val in cells.items():
            c, r = RowColOperations._parse_cell_ref(addr)
            new_r = r if r < row else r + 1
            new_addr = rc_to_address(new_r, c)
            new_cells[new_addr] = val
            if addr in styles:
                new_styles[new_addr] = styles[addr]
        state['cells'] = new_cells
        state['styles'] = new_styles
        state['total_rows'] = total_rows + 1
        state['merges'] = RowColOperations._shift_merges(merges, 'row', row, 1)
        return {'code': 0}

    @staticmethod
    async def _insert_col_left(state: dict, addrs: list[str]) -> dict:
        if not addrs:
            return {'code': 1, 'msg': 'No address'}
        col, _ = RowColOperations._parse_cell_ref(addrs[0])
        total_cols = state.get('total_cols', 10)
        cells = state.get('cells', {})
        styles = state.get('styles', {})
        merges = state.get('merges', {})
        new_cells = {}
        new_styles = {}
        for addr, val in cells.items():
            c, r = RowColOperations._parse_cell_ref(addr)
            new_c = c if c < col else c + 1
            new_addr = rc_to_address(r, new_c)
            new_cells[new_addr] = val
            if addr in styles:
                new_styles[new_addr] = styles[addr]
        state['cells'] = new_cells
        state['styles'] = new_styles
        state['total_cols'] = total_cols + 1
        state['merges'] = RowColOperations._shift_merges(merges, 'col', col, 1)
        return {'code': 0}

    @staticmethod
    def _shift_merges(merges: dict, axis: str, pos: int, delta: int) -> dict:
        new_merges = {}
        for merge_ref, info in merges.items():
            tl = info.get('topLeft', '')
            m = re.match(r'([A-Z]+)(\d+)', tl.upper())
            if not m:
                continue
            mc, mr = 0, 0
            for ch in m.group(1):
                mc = mc * 26 + (ord(ch) - 64)
            mc -= 1
            mr = int(m.group(2))

            if axis == 'row' and mr >= pos:
                mr += delta
            elif axis == 'col' and mc >= pos:
                mc += delta
            else:
                new_merges[merge_ref] = info
                continue

            new_tl = rc_to_address(mr, mc)
            new_ref = f'{new_tl}:'
            br_parts = merge_ref.split(':')
            if len(br_parts) == 2:
                br_m = re.match(r'([A-Z]+)(\d+)', br_parts[1].upper())
                if br_m:
                    bmc, bmr = 0, 0
                    for ch in br_m.group(1):
                        bmc = bmc * 26 + (ord(ch) - 64)
                    bmc -= 1
                    bmr = int(br_m.group(2))
                    if axis == 'row':
                        bmr += delta
                    elif axis == 'col':
                        bmc += delta
                    new_br = rc_to_address(bmr, bmc)
                    new_ref = f'{new_tl}:{new_br}'
            info['topLeft'] = new_tl
            new_merges[new_ref] = info
        return new_merges

    @staticmethod
    async def _delete_shift_right(state: dict, addrs: list[str]) -> dict:
        bounds = RowColOperations._bounds(addrs)
        if not bounds:
            return {'code': 1, 'msg': 'No address'}
        min_col, max_col, min_row, max_row = bounds
        width = max_col - min_col + 1

        def transform(col: int, row: int) -> str | None:
            if min_row <= row <= max_row and min_col <= col <= max_col:
                return None
            if min_row <= row <= max_row and col > max_col:
                return rc_to_address(row, col - width)
            return rc_to_address(row, col)

        RowColOperations._move_cell_maps(state, transform)
        RowColOperations._drop_merges_touching_bounds(state, min_col, max_col, min_row, max_row)
        return {'code': 0}

    @staticmethod
    async def _delete_shift_up(state: dict, addrs: list[str]) -> dict:
        bounds = RowColOperations._bounds(addrs)
        if not bounds:
            return {'code': 1, 'msg': 'No address'}
        min_col, max_col, min_row, max_row = bounds
        height = max_row - min_row + 1

        def transform(col: int, row: int) -> str | None:
            if min_col <= col <= max_col and min_row <= row <= max_row:
                return None
            if min_col <= col <= max_col and row > max_row:
                return rc_to_address(row - height, col)
            return rc_to_address(row, col)

        RowColOperations._move_cell_maps(state, transform)
        RowColOperations._drop_merges_touching_bounds(state, min_col, max_col, min_row, max_row)
        return {'code': 0}

    @staticmethod
    async def _insert_shift_right(state: dict, addrs: list[str]) -> dict:
        bounds = RowColOperations._bounds(addrs)
        if not bounds:
            return {'code': 1, 'msg': 'No address'}
        min_col, max_col, min_row, max_row = bounds
        width = max_col - min_col + 1

        def transform(col: int, row: int) -> str | None:
            if min_row <= row <= max_row and col >= min_col:
                return rc_to_address(row, col + width)
            return rc_to_address(row, col)

        RowColOperations._move_cell_maps(state, transform)
        state['total_cols'] = max(state.get('total_cols', 10) + width, max_col + width + 1)
        RowColOperations._drop_merges_touching_bounds(state, min_col, max_col, min_row, max_row)
        return {'code': 0}

    @staticmethod
    async def _insert_shift_down(state: dict, addrs: list[str]) -> dict:
        bounds = RowColOperations._bounds(addrs)
        if not bounds:
            return {'code': 1, 'msg': 'No address'}
        min_col, max_col, min_row, max_row = bounds
        height = max_row - min_row + 1

        def transform(col: int, row: int) -> str | None:
            if min_col <= col <= max_col and row >= min_row:
                return rc_to_address(row + height, col)
            return rc_to_address(row, col)

        RowColOperations._move_cell_maps(state, transform)
        state['total_rows'] = max(state.get('total_rows', 40) + height, max_row + height)
        RowColOperations._drop_merges_touching_bounds(state, min_col, max_col, min_row, max_row)
        return {'code': 0}

    @staticmethod
    async def _insert_row_below(state: dict, addrs: list[str]) -> dict:
        if not addrs:
            return {'code': 1, 'msg': 'No address'}
        _, row = RowColOperations._parse_cell_ref(addrs[0])
        return await RowColOperations._insert_row_above(state, [f'A{row + 1}'])

    @staticmethod
    async def _insert_col_right(state: dict, addrs: list[str]) -> dict:
        if not addrs:
            return {'code': 1, 'msg': 'No address'}
        col, _ = RowColOperations._parse_cell_ref(addrs[0])
        return await RowColOperations._insert_col_left(state, [rc_to_address(1, col + 1)])

    @staticmethod
    async def _merge(state: dict, addrs: list[str], params: dict) -> dict:
        merge_data = params.get('merges', {})
        state.setdefault('merges', {}).update(merge_data)
        return {'code': 0}

    @staticmethod
    async def _unmerge(state: dict, addrs: list[str]) -> dict:
        if not addrs:
            return {'code': 1, 'msg': 'No address'}
        addr = addrs[0]
        merges = state.get('merges', {})
        to_remove = []
        for merge_ref, info in merges.items():
            if info.get('topLeft') == addr:
                to_remove.append(merge_ref)
        for ref in to_remove:
            merges.pop(ref, None)
        return {'code': 0}

    @staticmethod
    async def _sort(state: dict, addrs: list[str], params: dict) -> dict:
        col = int(params.get('col', 0))
        order = params.get('order', 'asc')
        cells = state.get('cells', {})

        sorted_addrs = RowColOperations._sorted_addrs(state)
        rows: dict[int, dict[int, str]] = {}
        for r, c, addr in sorted_addrs:
            if r not in rows:
                rows[r] = {}
            rows[r][c] = cells[addr]

        sorted_rows = sorted(rows.items(), key=lambda x: str(x[1].get(col, '')), reverse=(order == 'desc'))
        new_cells = {}
        for new_r, (_, row_data) in enumerate(sorted_rows, 1):
            for c, val in row_data.items():
                new_addr = rc_to_address(new_r, c)
                new_cells[new_addr] = val
        state['cells'] = new_cells
        return {'code': 0}
