import subprocess
import json
from pathlib import Path
import fitz  # PyMuPDF

from src.strategies.base import BaseExtractor
from src.models.document import ExtractedDocument, Page, Block


class LayoutExtractor(BaseExtractor):
    """
    Workhorse for reports with tables, multi‑columns, and complex layouts.
    Uses Docling if available, otherwise Marker (--output-format json).
    """

    def __init__(self, config_path: str = "rubric/extraction_rules.yaml"):
        self.config_path = config_path
        self.engine = "docling"  # default; fallback to marker if not installed

    def extract(self, pdf_path: str, pages: list[int] | None = None) -> ExtractedDocument:
        pages_out = []
        document_id = Path(pdf_path).stem

        try:
            if self.engine == "docling":
                from docling.document_converter import DocumentConverter
                converter = DocumentConverter()

                # If batching requested, create a temporary PDF with only those pages
                if pages:
                    tmp_path = Path(pdf_path).with_suffix(".batch.pdf")
                    doc_in = fitz.open(pdf_path)
                    doc_out = fitz.open()
                    for p in pages:
                        doc_out.insert_pdf(doc_in, from_page=p-1, to_page=p-1)
                    doc_out.save(tmp_path)
                    doc_in.close()
                    doc_out.close()
                    result = converter.convert(str(tmp_path))
                else:
                    result = converter.convert(pdf_path)

                doc = result.document
                for page in doc.pages:
                    blocks = []
                    for b in page.blocks:
                        if b.type == "text":
                            blocks.append(Block(type="text", bbox=b.bbox, text=getattr(b, "text", None)))
                        elif b.type == "table":
                            blocks.append(Block(type="table", bbox=b.bbox, table_json=getattr(b, "table", None)))
                        elif b.type == "picture":
                            blocks.append(Block(type="figure", bbox=b.bbox, text=None))
                    pages_out.append(Page(page_number=page.page_no, blocks=blocks))

            else:
                # Marker fallback
                out_json = Path(pdf_path).with_suffix(".marker.json")
                cmd = ["marker", "--output-format", "json", pdf_path, "-o", str(out_json)]
                subprocess.run(cmd, check=True)
                with open(out_json, "r", encoding="utf-8") as f:
                    marker_doc = json.load(f)

                for i, page in enumerate(marker_doc.get("pages", []), start=1):
                    blocks = []
                    for blk in page.get("blocks", []):
                        blocks.append(Block(
                            type=blk.get("type", "text"),
                            bbox=blk.get("bbox", [0, 0, 0, 0]),
                            text=blk.get("text"),
                            table_json=blk.get("table_cells"),
                        ))
                    pages_out.append(Page(page_number=i, blocks=blocks))

        except Exception as e:
            blocks = [Block(type="error", bbox=[0, 0, 0, 0], text=f"Extraction failed: {e}")]
            pages_out.append(Page(page_number=0, blocks=blocks))

        return ExtractedDocument(document_id=document_id, pages=pages_out)

    def confidence(self, document: ExtractedDocument) -> float:
        score = 1.0
        total_blocks = sum(len(p.blocks) for p in document.pages)
        non_empty_blocks = sum(
            1 for p in document.pages for b in p.blocks if (b.text and b.text.strip()) or b.table_json
        )
        if total_blocks == 0:
            return 0.0
        ratio = non_empty_blocks / total_blocks
        if ratio < 0.8:
            score -= 0.2
        if ratio < 0.5:
            score -= 0.4
        return max(score, 0.0)

    def cost_estimate(self, pdf_path: str) -> dict:
        # Estimate $0.0005 per page
        try:
            from pdfplumber import open as pdf_open
            with pdf_open(pdf_path) as pdf:
                pages = len(pdf.pages)
        except Exception:
            pages = 1
        return {
            "estimated_cost_usd": round(pages * 0.0005, 6),
            "method": "layout_model"
        }
