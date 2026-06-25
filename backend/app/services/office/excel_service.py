import logging

logger = logging.getLogger(__name__)


class ExcelService:

    async def export(self, file_path: str, json_data: dict) -> None:
        from openpyxl import Workbook
        wb = Workbook()
        wb.remove(wb.active)

        sheets = json_data.get("sheets", [])
        if not sheets:
            inner = json_data.get("content", {})
            sheets = inner.get("sheets", []) if inner else []

        for sheet_data in sheets:
            ws = wb.create_sheet(title=sheet_data.get("name", "Sheet1"))
            cells = sheet_data.get("cells", {})
            for coord, info in cells.items():
                if info.get("type") == "null":
                    continue
                ws[coord] = info.get("value")

        wb.save(file_path)
