import re
import sqlite3
import uuid
import hashlib
from typing import List, Optional

from src.models.query import StructuredFact, ProvenanceCitation
from src.models.document import ExtractedDocument


class FactTableBuilder:
    KEYWORDS = ["budget", "expenditure", "allocation", "amount", "fy", "year"]

    def __init__(self, db_path: str = ".refinery/fact_table.db"):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        cur.execute("""
        CREATE TABLE IF NOT EXISTS facts (
            fact_id TEXT PRIMARY KEY,
            document_id TEXT,
            page INTEGER,
            fact_type TEXT,
            value REAL,
            unit TEXT,
            year INTEGER,
            description TEXT,
            provenance_document TEXT,
            provenance_page INTEGER,
            provenance_bbox TEXT,
            provenance_quote TEXT,
            provenance_hash TEXT
        )
        """)
        conn.commit()
        conn.close()

    def build(self, extracted_doc: ExtractedDocument) -> List[StructuredFact]:
        facts: List[StructuredFact] = []
        doc_label = getattr(extracted_doc, "doc_name", extracted_doc.document_id)

        for page in extracted_doc.pages:
            for block in page.blocks:
                # Handle tables
                if getattr(block, "table_json", None):
                    headers = [h.lower() for h in block.table_json.get("headers", [])]
                    if any(any(kw in h for kw in self.KEYWORDS) for h in headers):
                        for row in block.table_json.get("rows", []):
                            for col_idx, cell in enumerate(row):
                                if self._is_number(cell):
                                    fact_type = self._infer_fact_type(headers[col_idx])
                                    unit = self._infer_unit(headers[col_idx])
                                    year = self._extract_year(headers)
                                    description = f"{headers[col_idx]}: {cell}"
                                    provenance = ProvenanceCitation(
                                        document_name=doc_label,
                                        page_number=page.page_number,
                                        bbox=tuple(block.bbox),
                                        exact_quote=str(cell),
                                        content_hash=getattr(block, "content_hash", self._hash_text(str(cell)))
                                    )
                                    facts.append(StructuredFact(
                                        fact_id=str(uuid.uuid4()),
                                        document_id=extracted_doc.document_id,
                                        page=page.page_number,
                                        fact_type=fact_type,
                                        value=float(cell),
                                        unit=unit,
                                        year=year,
                                        description=description,
                                        provenance=provenance
                                    ))

                # Handle text blocks
                elif getattr(block, "text", None):
                    text = block.text
                    text_lower = text.lower()
                    if any(kw in text_lower for kw in self.KEYWORDS):
                        numbers = re.findall(r"\d+(?:\.\d+)?", text)
                        for num in numbers:
                            # Require currency or financial context
                            if not any(cur in text_lower for cur in ["birr", "etb", "usd", "dollar", "%", "percent"]):
                                continue
                            provenance = ProvenanceCitation(
                                document_name=doc_label,
                                page_number=page.page_number,
                                bbox=tuple(block.bbox),
                                exact_quote=text.strip()[:200],
                                content_hash=self._hash_text(text)
                            )
                            facts.append(StructuredFact(
                                fact_id=str(uuid.uuid4()),
                                document_id=extracted_doc.document_id,
                                page=page.page_number,
                                fact_type="expenditure",
                                value=float(num),
                                unit=self._infer_unit(text_lower),
                                year=self._extract_year([text_lower]),
                                description=text.strip()[:200],
                                provenance=provenance
                            ))

        self._persist(facts)
        return facts

    def _persist(self, facts: List[StructuredFact]):
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        for fact in facts:
            cur.execute("""
            INSERT OR REPLACE INTO facts VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                fact.fact_id,
                fact.document_id,
                fact.page,
                fact.fact_type,
                fact.value,
                fact.unit,
                fact.year,
                fact.description,
                fact.provenance.document_name,
                fact.provenance.page_number,
                str(fact.provenance.bbox),
                fact.provenance.exact_quote,
                fact.provenance.content_hash
            ))
        conn.commit()
        conn.close()

    def _is_number(self, val: str) -> bool:
        try:
            num = float(val)
            # Ignore small integers that are likely page numbers or list indices
            if num.is_integer() and abs(num) < 10:
                return False
            return True
        except Exception:
            return False

    def _infer_fact_type(self, header: str) -> str:
        h = header.lower()
        if "budget" in h: return "budget"
        if "expenditure" in h or "spent" in h: return "expenditure"
        if "allocation" in h: return "allocation"
        if "funds" in h or "grant" in h: return "funds"
        if "procurement" in h: return "procurement"
        if "spending" in h or "cost" in h: return "expenditure"
        return "numeric"

    def _infer_unit(self, context: str) -> Optional[str]:
        if "birr" in context:
            return "ETB"
        if "usd" in context or "dollar" in context:
            return "USD"
        if "%" in context or "percent" in context:
            return "%"
        return None

    def _extract_year(self, headers: List[str]) -> Optional[int]:
        for h in headers:
            match = re.search(r"(20\d{2})", h)
            if match:
                return int(match.group(1))
        return None

    def _hash_text(self, text: str) -> str:
        return hashlib.sha256(text.encode("utf-8")).hexdigest()
