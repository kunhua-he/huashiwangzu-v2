import logging
from docx import Document

logger = logging.getLogger(__name__)


class DocxService:

    async def export(self, file_path: str, json_content: dict) -> None:
        doc = Document()
        content = json_content.get("content", json_content) if isinstance(json_content, dict) else json_content

        if isinstance(content, list):
            for item in content:
                if item.get("type") == "paragraph":
                    doc.add_paragraph(item.get("content", ""))
                elif item.get("type") == "table":
                    rows = item.get("rows", [])
                    if rows:
                        table = doc.add_table(rows=len(rows), cols=len(rows[0].get("cells", [])))
                        for i, row_data in enumerate(rows):
                            for j, cell_text in enumerate(row_data.get("cells", [])):
                                if j < len(table.columns):
                                    table.cell(i, j).text = cell_text

        doc.save(file_path)

    def preview_patch(self, json_content: dict, patch: dict) -> dict:
        if patch.get("operation_type") not in ("replace_text", "modify_docx_paragraph"):
            raise ValueError("DOCX 补丁仅支持 replace_text 操作类型")

        content = json_content.get("content", json_content) if isinstance(json_content, dict) else json_content
        target_id = None
        if isinstance(content, list):
            for item in content:
                if item.get("type") == "paragraph" and item.get("content", "").strip():
                    target_id = item["id"]
                    break

        return {
            "preview_passed": True,
            "target_id": target_id,
            "risk_level": "medium",
            "style_loss_risk": True,
        }
