import time
import pdfplumber

from src.strategies.base import BaseExtractor
from src.models.document import ExtractedDocument, Page, Block


class FastTextExtractor(BaseExtractor):
    """
    Cheap, fast path for clean digital documents.
    Uses pdfplumber to extract text and tables.
    """

    def extract(self, pdf_path: str, pages: list[int] | None = None) -> ExtractedDocument:
        start_time = time.time()
        pages_out = []

        with pdfplumber.open(pdf_path) as pdf:
            target_pages = pdf.pages if pages is None else [pdf.pages[i - 1] for i in pages]

            for idx, page in enumerate(target_pages, start=1):
                blocks = []

                # Text blocks
                text = page.extract_text(x_tolerance=2, y_tolerance=2) or ""
                if text.strip():
                    bbox = [0, 0, page.width, page.height]
                    blocks.append(Block(type="text", bbox=bbox, text=text))

                # Table blocks
                tables = page.extract_tables()
                for t in tables:
                    bbox = [0, 0, page.width, page.height]  # pdfplumber doesn't give table bbox directly
                    blocks.append(Block(type="table", bbox=bbox, table_json={"rows": t}))

                pages_out.append(Page(page_number=idx, blocks=blocks))

        document_id = pdf_path.split("/")[-1].split(".")[0]
        return ExtractedDocument(document_id=document_id, pages=pages_out)

    def confidence(self, document: ExtractedDocument) -> float:
        """
        Compute confidence score:
        - Start at 1.0
        - Deduct 0.2 if avg char density < 0.05
        - Deduct 0.1 for each page with zero characters
        """
        score = 1.0
        total_chars = 0
        total_area = 0
        zero_char_pages = 0

        for page in document.pages:
            page_chars = sum(len(b.text or "") for b in page.blocks if b.type == "text")
            total_chars += page_chars
            # assume full page area ~1 for density (simplified)
            total_area += 1
            if page_chars == 0:
                zero_char_pages += 1

        avg_density = (total_chars / total_area) if total_area > 0 else 0
        if avg_density < 0.05:
            score -= 0.2
        score -= 0.1 * zero_char_pages

        return max(score, 0.0)

    def cost_estimate(self, pdf_path: str) -> dict:
        """
        Estimate cost: $0.0001 per page.
        """
        with pdfplumber.open(pdf_path) as pdf:
            pages = len(pdf.pages)
        return {
            "estimated_cost_usd": round(pages * 0.0001, 6),
            "method": "fast_text"
        }
