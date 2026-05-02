import time
import json
from pathlib import Path
from typing import Optional
import io

import pdfplumber
from pdf2image import convert_from_path

from src.strategies.base import BaseExtractor
from src.models.document import ExtractedDocument, Page, Block
from src.tools.cost_guard import BudgetGuard


class VisionExtractor(BaseExtractor):
    """
    Safety net strategy for scanned, handwritten, or degraded documents.
    Uses a Vision-Language Model (VLM) via OpenRouter or Ollama.
    """

    def __init__(self, config_path: str = "rubric/extraction_rules.yaml"):
        import yaml
        with open(config_path, "r", encoding="utf-8") as f:
            cfg = yaml.safe_load(f)
        self.vlm_provider = cfg.get("vlm_provider", "openrouter")
        self.model_name = cfg.get("model_name", "gpt-4-vision")
        self.max_cost_per_page = cfg.get("max_cost_per_page", 0.01)
        self.max_cost_per_document = cfg.get("max_cost_per_document", 1.00)

        # Budget guard handles per-document tracking
        self.budget_guard = BudgetGuard(self.max_cost_per_document)

    def extract(self, pdf_path: str, pages: Optional[list[int]] = None) -> ExtractedDocument:
        document_id = Path(pdf_path).stem
        pages_out = []
        failure_reason = None

        try:
            images = convert_from_path(pdf_path, dpi=200)
            target_pages = images if pages is None else [images[i] for i in pages]

            for idx, img in enumerate(target_pages, start=1):
                # Budget guard check
                if self.budget_guard.is_exceeded(document_id):
                    failure_reason = "budget_capped"
                    break

                est_cost = self.max_cost_per_page

                # Convert image to bytes
                buf = io.BytesIO()
                img.save(buf, format="JPEG")
                img_bytes = buf.getvalue()

                # Call VLM
                response_text = self._call_vlm(img_bytes)

                # Try to parse JSON
                try:
                    parsed = json.loads(response_text)
                    blocks = []
                    for blk in parsed.get("blocks", []):
                        blocks.append(Block(
                            type=blk.get("type", "text"),
                            bbox=blk.get("bbox", [0, 0, 0, 0]),
                            text=blk.get("text"),
                            table_json=blk.get("table_json"),
                            entities=blk.get("entities"),
                        ))
                    pages_out.append(Page(page_number=idx, blocks=blocks))
                except Exception:
                    # Fallback: raw text block
                    blocks = [Block(type="text", bbox=[0, 0, 0, 0], text=response_text)]
                    pages_out.append(Page(page_number=idx, blocks=blocks))

                # Track cost after each page
                self.budget_guard.track(est_cost, document_id)

        except Exception as e:
            failure_reason = f"extraction_failed: {e}"
            blocks = [Block(type="error", bbox=[0, 0, 0, 0], text=str(e))]
            pages_out.append(Page(page_number=0, blocks=blocks))

        return ExtractedDocument(document_id=document_id, pages=pages_out)

    
    def _call_vlm(self, img_bytes: bytes) -> str:
        """
        Call the configured VLM provider.
        """
        if self.vlm_provider == "openrouter":
            from openai import OpenAI
            client = OpenAI(base_url="https://openrouter.ai/api/v1")
            resp = client.chat.completions.create(
                model=self.model_name,
                messages=[{
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "Extract all text, tables, and key entities. "
                                                  "Output JSON matching ExtractedDocument schema."},
                        {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64," + img_bytes.decode("latin1")}}
                    ]
                }],
            )
            return resp.choices[0].message.content

        elif self.vlm_provider == "ollama":
            import ollama
            resp = ollama.chat(model=self.model_name, messages=[
                {"role": "user", "content": "Extract all text, tables, and key entities. "
                                            "Output JSON matching ExtractedDocument schema."}
            ])
            return resp["message"]["content"]

        else:
            raise ValueError(f"Unsupported VLM provider: {self.vlm_provider}")

    def confidence(self, document: ExtractedDocument) -> float:
        total_blocks = sum(len(p.blocks) for p in document.pages)
        non_empty_blocks = sum(
            1 for p in document.pages for b in p.blocks if (b.text and b.text.strip()) or b.table_json
        )
        if total_blocks == 0:
            return 0.0
        return non_empty_blocks / total_blocks

    def cost_estimate(self, pdf_path: str) -> dict:
        try:
            with pdfplumber.open(pdf_path) as pdf:
                pages = len(pdf.pages)
        except Exception:
            pages = 1
        return {
            "estimated_cost_usd": round(pages * self.max_cost_per_page, 6),
            "method": "vision_model"
        }

