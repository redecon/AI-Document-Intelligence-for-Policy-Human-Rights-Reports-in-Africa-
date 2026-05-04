import hashlib
import yaml
from pathlib import Path
from typing import List
from collections import Counter

import tiktoken  # for OpenAI tokenizer
import spacy     # lightweight NER
from src.models.document import ExtractedDocument
from src.models.chunk import LogicalDocumentUnit, Entity
from src.models.provenance import Bbox


class ChunkingEngine:
    def __init__(self, config_path: str = "rubric/chunking_rules.yaml"):
        with open(config_path, "r", encoding="utf-8") as f:
            cfg = yaml.safe_load(f)
        self.rules = cfg["rules"]

        # Tokenizer setup
        tokenizer_name = self.rules.get("tokenizer", "cl100k_base")
        if tokenizer_name == "cl100k_base":
            self.tokenizer = tiktoken.get_encoding("cl100k_base")
        else:
            # fallback: HuggingFace tokenizer
            from transformers import AutoTokenizer
            self.tokenizer = AutoTokenizer.from_pretrained(tokenizer_name)

        # Lightweight NER
        self.ner = spacy.load("en_core_web_sm")

    def chunk(self, document: ExtractedDocument) -> List[LogicalDocumentUnit]:
        ldus = []
        section_context = []

        # Step 1: Flatten document tree
        items = self._flatten(document)

        # Step 2: Group into LDUs
        for item in items:
            ldu = self._group_item(item, section_context)
            if ldu:
                # Step 3: Enforce chunking constitution
                ldu = self._enforce_rules(ldu)

                # Step 4: Enrich with entities and topics
                ldu.entities_detected = self._extract_entities(ldu.content)
                ldu.topics = self._assign_topics(ldu.content)

                # Step 5: Resolve cross-references
                ldu.cross_references = self._resolve_cross_refs(ldu.content, ldus)

                # Step 6: Generate embed_text (tables/figures)
                if self.rules.get("embed_text_generation", False):
                    if ldu.chunk_type in ["table", "figure"]:
                        ldu.embed_text = self._generate_embed_text(ldu.content)

                # Step 7: Compute content_hash
                ldu.content_hash = self._hash(ldu)

                # Step 8: Validate
                self._validate(ldu)

                ldus.append(ldu)

        return ldus

    def _flatten(self, document: ExtractedDocument):
        # Traverse document.pages and blocks in reading order
        items = []
        for page in document.pages:
            for block in page.blocks:
                items.append({
                    "page": page.page_number,
                    "block": block,
                    "section": block.section_path if hasattr(block, "section_path") else []
                })
        return items

    def _group_item(self, item, section_context):
        # Apply grouping rules: tables, figures, quotes, lists, text
        blk = item["block"]
        if blk.type == "table":
            return LogicalDocumentUnit(
                chunk_id="",
                content=blk.text or "",
                chunk_type="table",
                page_refs=[item["page"]],
                bounding_boxes=[Bbox(x0=blk.bbox[0], y0=blk.bbox[1], x1=blk.bbox[2], y1=blk.bbox[3], page=item["page"])],
                parent_section=section_context,
                entities_detected=[],
                topics=[],
                token_count=0,
                content_hash="",
            )
        elif blk.type == "text":
            return LogicalDocumentUnit(
                chunk_id="",
                content=blk.text or "",
                chunk_type="text",
                page_refs=[item["page"]],
                bounding_boxes=[Bbox(x0=blk.bbox[0], y0=blk.bbox[1], x1=blk.bbox[2], y1=blk.bbox[3], page=item["page"])],
                parent_section=section_context,
                entities_detected=[],
                topics=[],
                token_count=0,
                content_hash="",
            )
        # Extend for figures, quotes, lists...
        return None

    def _enforce_rules(self, ldu: LogicalDocumentUnit) -> LogicalDocumentUnit:
        tokens = self.tokenizer.encode(ldu.content)
        ldu.token_count = len(tokens)
        max_tokens = self.rules.get("max_tokens_per_chunk", 512)
        overlap = self.rules.get("overlap_tokens", 50)

        if ldu.token_count > max_tokens:
            if ldu.chunk_type == "table" and self.rules.get("table_never_split", True):
                # Split by rows, repeat header
                pass
            elif ldu.chunk_type == "text":
                # Split at paragraph boundaries with overlap
                pass
            elif ldu.chunk_type == "legal_clause" and self.rules.get("clause_never_split", True):
                # Mark warning
                ldu.sensitivity_flag = "high"
        return ldu

    def _extract_entities(self, text: str) -> List[Entity]:
        doc = self.ner(text)
        return [Entity(type=ent.label_, text=ent.text, confidence=1.0) for ent in doc.ents]

    def _assign_topics(self, text: str) -> List[str]:
        # Load civic keywords
        with open("rubric/civic_keywords.yaml", "r", encoding="utf-8") as f:
            keywords = yaml.safe_load(f)
        topics = []
        for domain, terms in keywords.items():
            if any(term.lower() in text.lower() for term in terms):
                topics.append(domain)
        return topics

    def _resolve_cross_refs(self, text: str, ldus: List[LogicalDocumentUnit]) -> List[str]:
        refs = []
        # Simple regex for "see Section X"
        import re
        matches = re.findall(r"see (Section|Table|Annex) (\w+)", text, flags=re.IGNORECASE)
        for m in matches:
            # naive resolution: check if any LDU has matching title/id
            for l in ldus:
                if m[1] in l.content:
                    refs.append(l.chunk_id)
        return refs

    def _generate_embed_text(self, content: str) -> str:
        # Placeholder: call a fast LLM or heuristic summarizer
        return f"Summary description of {content[:50]}..."

    def _hash(self, ldu: LogicalDocumentUnit) -> str:
        h = hashlib.sha256()
        h.update(ldu.content.encode("utf-8"))
        h.update(str(ldu.page_refs).encode("utf-8"))
        h.update(str(ldu.bounding_boxes).encode("utf-8"))
        return h.hexdigest()

    def _validate(self, ldu: LogicalDocumentUnit):
        # Check constitution rules
        if ldu.chunk_type == "table" and not ldu.content:
            print(f"Warning: empty table chunk {ldu.chunk_id}")
