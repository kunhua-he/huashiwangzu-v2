"""Database operations for state persistence - 1:1 from old state_* traits."""
import json
from datetime import datetime
from typing import Optional

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import (
    ExcelCell,
    ExcelColWidth,
    ExcelHistory,
    ExcelRedoStack,
    ExcelRowHeight,
    ExcelSheet,
    ExcelVersion,
    ExcelWorkbook,
)
from ..tool.config import AUTO_SAVE_INTERVAL, DEFAULT_TOTAL_COLS, DEFAULT_TOTAL_ROWS
from .manager import build_snapshot


async def find_workbook(db: AsyncSession, state_key: str) -> Optional[dict]:
    result = await db.execute(select(ExcelWorkbook).where(ExcelWorkbook.state_key == state_key))
    wb = result.scalar_one_or_none()
    if wb:
        return {'id': wb.id, 'name': wb.name, 'owner_id': wb.owner_id}
    return None


async def find_or_create_workbook(db: AsyncSession, state_key: str, owner_id: int = 0) -> dict:
    wb = await find_workbook(db, state_key)
    if wb:
        return wb
    new_wb = ExcelWorkbook(state_key=state_key, name=state_key, owner_id=owner_id, upload_time=datetime.utcnow(), last_active_time=datetime.utcnow())
    db.add(new_wb)
    await db.commit()
    await db.refresh(new_wb)
    return {'id': new_wb.id, 'name': new_wb.name, 'owner_id': new_wb.owner_id}


async def find_sheet(db: AsyncSession, workbook_id: int, name: str) -> Optional[dict]:
    result = await db.execute(select(ExcelSheet).where(ExcelSheet.workbook_id == workbook_id, ExcelSheet.name == name))
    sheet = result.scalar_one_or_none()
    return {'id': sheet.id, 'name': sheet.name, 'total_rows': sheet.total_rows, 'total_cols': sheet.total_cols} if sheet else None


async def find_or_create_sheet(db: AsyncSession, workbook_id: int, name: str, total_rows: int = DEFAULT_TOTAL_ROWS, total_cols: int = DEFAULT_TOTAL_COLS) -> dict:
    sheet = await find_sheet(db, workbook_id, name)
    if sheet:
        return sheet
    new_sheet = ExcelSheet(workbook_id=workbook_id, name=name, total_rows=total_rows, total_cols=total_cols)
    db.add(new_sheet)
    await db.commit()
    await db.refresh(new_sheet)
    return {'id': new_sheet.id, 'name': new_sheet.name, 'total_rows': new_sheet.total_rows, 'total_cols': new_sheet.total_cols}


async def sync_cells(db: AsyncSession, sheet_id: int, cells: dict[str, str], styles: dict, merges: dict):
    await db.execute(text(f"DELETE FROM {ExcelCell.__tablename__} WHERE sheet_id = :sid"), {'sid': sheet_id})
    for addr, val in cells.items():
        style_json = json.dumps(styles.get(addr, {}), ensure_ascii=False) if addr in styles else None
        merge_info = None
        for merge_ref, md in merges.items():
            if md.get('topLeft') == addr:
                merge_info = json.dumps({'merged': True, 'type': '主格', 'range': merge_ref, 'rows': md.get('rows', 1), 'cols': md.get('cols', 1)}, ensure_ascii=False)
                break
        db.add(ExcelCell(sheet_id=sheet_id, cell_addr=addr, cell_value=val, style_json=style_json, merge_info=merge_info))
    await db.commit()


async def sync_col_widths(db: AsyncSession, sheet_id: int, col_widths: dict[str, int]):
    await db.execute(text(f"DELETE FROM {ExcelColWidth.__tablename__} WHERE sheet_id = :sid"), {'sid': sheet_id})
    for col_letter, width in col_widths.items():
        ci = 0
        for ch in col_letter:
            ci = ci * 26 + (ord(ch) - 64)
        ci -= 1
        db.add(ExcelColWidth(sheet_id=sheet_id, col_index=ci, width=width))
    await db.commit()


async def sync_row_heights(db: AsyncSession, sheet_id: int, row_heights: dict[str, int]):
    await db.execute(text(f"DELETE FROM {ExcelRowHeight.__tablename__} WHERE sheet_id = :sid"), {'sid': sheet_id})
    for row_str, height in row_heights.items():
        db.add(ExcelRowHeight(sheet_id=sheet_id, row_index=int(row_str), height=height))
    await db.commit()


async def read_history(db: AsyncSession, state_key: str) -> list[dict]:
    wb = await find_workbook(db, state_key)
    if not wb:
        return []
    sheet = await find_sheet(db, wb['id'], 'Sheet1')
    if not sheet:
        return []
    result = await db.execute(text(f"SELECT id, action, cell_addr, description, created_at FROM {ExcelHistory.__tablename__} WHERE sheet_id = :sid ORDER BY id"), {'sid': sheet['id']})
    return [{'id': r[0], 'action': r[1], 'cell_addr': r[2], 'description': r[3], 'created_at': r[4].isoformat() if r[4] else ''} for r in result.fetchall()]


async def record_snapshot(db: AsyncSession, state: dict, state_key: str, action: str, addr: str = '', description: str = '', owner_id: int = 0):
    sheet_id = state.get('_sheet_id')
    if not sheet_id:
        wb = await find_or_create_workbook(db, state_key, owner_id)
        sheet = await find_sheet(db, wb['id'], state.get('_current_sheet', 'Sheet1'))
        sheet_id = sheet['id'] if sheet else None
    if not sheet_id:
        return
    snapshot = build_snapshot(state)
    db.add(ExcelHistory(sheet_id=sheet_id, action=action, cell_addr=addr, description=description, snapshot_json=json.dumps(snapshot, ensure_ascii=False)))
    await db.commit()
    result = await db.execute(text(f"SELECT COUNT(*) FROM {ExcelHistory.__tablename__} WHERE sheet_id = :sid"), {'sid': sheet_id})
    count = result.scalar() or 0
    if count > 0 and count % AUTO_SAVE_INTERVAL == 0 and state_key.startswith('knowledge_'):
        file_id = int(state_key.replace('knowledge_', ''))
        db.add(ExcelVersion(file_id=file_id, version_name=f"{datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} (auto)", snapshot_json=json.dumps(build_snapshot(state), ensure_ascii=False), operation_steps=count))
        await db.commit()


async def undo_operation(db: AsyncSession, state: dict, state_key: str) -> bool:
    sheet_id = state.get('_sheet_id')
    if not sheet_id:
        return False
    result = await db.execute(text(f"SELECT id, action, cell_addr, snapshot_json FROM {ExcelHistory.__tablename__} WHERE sheet_id = :sid ORDER BY id DESC LIMIT 1"), {'sid': sheet_id})
    last = result.fetchone()
    if not last:
        return False
    snapshot = json.loads(last[3]) if last[3] else None
    if not isinstance(snapshot, dict):
        return False
    db.add(ExcelRedoStack(sheet_id=sheet_id, action=last[1], cell_addr=last[2], snapshot_json=json.dumps(build_snapshot(state), ensure_ascii=False)))
    await db.execute(text(f"DELETE FROM {ExcelHistory.__tablename__} WHERE id = :hid"), {'hid': last[0]})
    await db.commit()
    state['cells'] = snapshot.get('cells', {})
    state['styles'] = snapshot.get('styles', {})
    state['merges'] = snapshot.get('merges', {})
    state['col_widths'] = snapshot.get('col_widths', {})
    state['row_heights'] = snapshot.get('row_heights', {})
    state['total_rows'] = snapshot.get('total_rows', DEFAULT_TOTAL_ROWS)
    state['total_cols'] = snapshot.get('total_cols', DEFAULT_TOTAL_COLS)
    await sync_cells(db, sheet_id, state['cells'], state['styles'], state['merges'])
    await sync_col_widths(db, sheet_id, state['col_widths'])
    await sync_row_heights(db, sheet_id, state['row_heights'])
    return True


async def redo_operation(db: AsyncSession, state: dict, state_key: str) -> bool:
    sheet_id = state.get('_sheet_id')
    if not sheet_id:
        return False
    result = await db.execute(text(f"SELECT id, action, cell_addr, snapshot_json FROM {ExcelRedoStack.__tablename__} WHERE sheet_id = :sid ORDER BY id DESC LIMIT 1"), {'sid': sheet_id})
    last = result.fetchone()
    if not last:
        return False
    snapshot = json.loads(last[3]) if last[3] else None
    if not isinstance(snapshot, dict):
        return False
    db.add(ExcelHistory(sheet_id=sheet_id, action=last[1], cell_addr=last[2], snapshot_json=json.dumps(build_snapshot(state), ensure_ascii=False)))
    await db.execute(text(f"DELETE FROM {ExcelRedoStack.__tablename__} WHERE id = :rid"), {'rid': last[0]})
    await db.commit()
    state['cells'] = snapshot.get('cells', {})
    state['styles'] = snapshot.get('styles', {})
    state['merges'] = snapshot.get('merges', {})
    state['col_widths'] = snapshot.get('col_widths', {})
    state['row_heights'] = snapshot.get('row_heights', {})
    state['total_rows'] = snapshot.get('total_rows', DEFAULT_TOTAL_ROWS)
    state['total_cols'] = snapshot.get('total_cols', DEFAULT_TOTAL_COLS)
    await sync_cells(db, sheet_id, state['cells'], state['styles'], state['merges'])
    await sync_col_widths(db, sheet_id, state['col_widths'])
    await sync_row_heights(db, sheet_id, state['row_heights'])
    return True


async def history_preview(db: AsyncSession, history_id: int, sheet_id: int) -> Optional[dict]:
    result = await db.execute(text(f"SELECT snapshot_json FROM {ExcelHistory.__tablename__} WHERE id = :hid AND sheet_id = :sid"), {'hid': history_id, 'sid': sheet_id})
    row = result.fetchone()
    if not row:
        return None
    snapshot = json.loads(row[0]) if row[0] else None
    return snapshot if isinstance(snapshot, dict) else None


async def read_state_full(db: AsyncSession, state_key: str, sheet_name: str = 'Sheet1', owner_id: int = 0) -> dict:
    wb = await find_or_create_workbook(db, state_key, owner_id)
    sheet = await find_or_create_sheet(db, wb['id'], sheet_name)
    sheet_id = sheet['id']

    result = await db.execute(text(f"SELECT cell_addr, cell_value, style_json, merge_info FROM {ExcelCell.__tablename__} WHERE sheet_id = :sid"), {'sid': sheet_id})
    cells = {}
    styles = {}
    merges = {}
    for r in result.fetchall():
        addr, val, sj, mi = r[0], r[1] or '', r[2], r[3]
        cells[addr] = val
        if sj:
            styles[addr] = json.loads(sj)
        if mi:
            mi_data = json.loads(mi)
            if mi_data.get('merged') and mi_data.get('type') == '主格':
                range_str = mi_data.get('range', '')
                if range_str:
                    merges[range_str] = {'topLeft': range_str.split(':')[0], 'rows': mi_data.get('rows', 1), 'cols': mi_data.get('cols', 1)}

    result = await db.execute(text(f"SELECT col_index, width FROM {ExcelColWidth.__tablename__} WHERE sheet_id = :sid"), {'sid': sheet_id})
    cw = {}
    for r in result.fetchall():
        letter = ''
        t = r[0] + 1
        while t > 0:
            t -= 1
            letter = chr(65 + (t % 26)) + letter
            t //= 26
        cw[letter] = int(r[1])

    result = await db.execute(text(f"SELECT row_index, height FROM {ExcelRowHeight.__tablename__} WHERE sheet_id = :sid"), {'sid': sheet_id})
    rh = {}
    for r in result.fetchall():
        rh[str(r[0])] = int(r[1])

    result = await db.execute(text(f"SELECT name FROM {ExcelSheet.__tablename__} WHERE workbook_id = :wid ORDER BY id"), {'wid': wb['id']})
    all_sheets = [r[0] for r in result.fetchall()]

    sheet_set = {}
    for s_name in all_sheets:
        if s_name == sheet_name:
            sheet_set[s_name] = {'cells': cells, 'styles': styles, 'merges': merges, 'col_widths': cw, 'row_heights': rh, 'total_rows': sheet['total_rows'], 'total_cols': sheet['total_cols']}
        else:
            other = await find_sheet(db, wb['id'], s_name)
            if other:
                sheet_set[s_name] = await read_sheet_full(db, other['id'], other['total_rows'], other['total_cols'])

    return {'filename': state_key, 'total_rows': sheet['total_rows'], 'total_cols': sheet['total_cols'],
            'cells': cells, 'styles': styles, 'merges': merges, 'col_widths': cw, 'row_heights': rh,
            'sheet_set': sheet_set, 'all_sheets': all_sheets, '_current_sheet': sheet_name,
            '_workbook_id': wb['id'], '_sheet_id': sheet_id}


async def read_sheet_full(db: AsyncSession, sheet_id: int, total_rows: int, total_cols: int) -> dict:
    result = await db.execute(text(f"SELECT cell_addr, cell_value, style_json, merge_info FROM {ExcelCell.__tablename__} WHERE sheet_id = :sid"), {'sid': sheet_id})
    cells = {}
    styles = {}
    merges = {}
    for r in result.fetchall():
        addr, val, sj, mi = r[0], r[1] or '', r[2], r[3]
        cells[addr] = val
        if sj:
            styles[addr] = json.loads(sj)
        if mi:
            mi_data = json.loads(mi)
            if mi_data.get('merged') and mi_data.get('type') == '主格' and mi_data.get('range'):
                merges[mi_data['range']] = {'topLeft': mi_data['range'].split(':')[0], 'rows': mi_data.get('rows', 1), 'cols': mi_data.get('cols', 1)}

    result = await db.execute(text(f"SELECT col_index, width FROM {ExcelColWidth.__tablename__} WHERE sheet_id = :sid"), {'sid': sheet_id})
    cw = {}
    for r in result.fetchall():
        letter = ''
        t = r[0] + 1
        while t > 0:
            t -= 1
            letter = chr(65 + (t % 26)) + letter
            t //= 26
        cw[letter] = int(r[1])

    result = await db.execute(text(f"SELECT row_index, height FROM {ExcelRowHeight.__tablename__} WHERE sheet_id = :sid"), {'sid': sheet_id})
    rh = {}
    for r in result.fetchall():
        rh[str(r[0])] = int(r[1])

    return {'cells': cells, 'styles': styles, 'merges': merges, 'col_widths': cw, 'row_heights': rh, 'total_rows': total_rows, 'total_cols': total_cols}


def empty_state(sheet_name: str = 'Sheet1') -> dict:
    return {'cells': {}, 'styles': {}, 'merges': {}, 'col_widths': {}, 'row_heights': {},
            'total_rows': DEFAULT_TOTAL_ROWS, 'total_cols': DEFAULT_TOTAL_COLS,
            'sheet_set': {}, 'all_sheets': [sheet_name], '_current_sheet': sheet_name}


async def archive_workbook(db: AsyncSession, state: dict, state_key: str, output_dir: str):
    wb = await find_workbook(db, state_key)
    if not wb:
        return None
    from ..engine.xlsx_generator import generate_xlsx
    name = wb['name']
    result = await db.execute(text(f"SELECT id, name, total_rows, total_cols FROM {ExcelSheet.__tablename__} WHERE workbook_id = :wid ORDER BY id"), {'wid': wb['id']})
    sheets = result.fetchall()
    if not sheets:
        await db.execute(text(f"DELETE FROM {ExcelWorkbook.__tablename__} WHERE id = :wid"), {'wid': wb['id']})
        await db.commit()
        return None
    all_sheet_data = {}
    for s in sheets:
        all_sheet_data[s[1]] = await read_sheet_full(db, s[0], s[2], s[3])
    import os.path
    filename = f"{name}.xlsx"
    output_path = os.path.join(output_dir, filename)
    success = generate_xlsx(output_path, all_sheet_data, filename)
    if not success:
        return None
    for s in sheets:
        sid = s[0]
        await db.execute(text(f"DELETE FROM {ExcelCell.__tablename__} WHERE sheet_id = :sid"), {'sid': sid})
        await db.execute(text(f"DELETE FROM {ExcelColWidth.__tablename__} WHERE sheet_id = :sid"), {'sid': sid})
        await db.execute(text(f"DELETE FROM {ExcelRowHeight.__tablename__} WHERE sheet_id = :sid"), {'sid': sid})
    await db.execute(text(f"DELETE FROM {ExcelSheet.__tablename__} WHERE workbook_id = :wid"), {'wid': wb['id']})
    await db.execute(text(f"DELETE FROM {ExcelWorkbook.__tablename__} WHERE id = :wid"), {'wid': wb['id']})
    await db.commit()
    return {'file': filename, 'path': output_path}
