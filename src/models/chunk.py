from typing import List, Literal, Dict,  Optional
from pydantic import BaseModel
from src.models.provenance import Bbox

class Entity(BaseModel):
    type: str
    text: str
    confidence: float

class SectionPath(BaseModel):
    level: int
    title: str

class LogicalDocumentUnit(BaseModel):
    chunk_id: str  # unique, derived from content hash
    content: str   # full text of the unit
    chunk_type: Literal[
        "text", "table", "legal_clause", "finding",
        "quote", "evidence_unit", "figure"
    ]
    page_refs: List[int]
    bounding_boxes: List[Bbox]
    parent_section: List[Dict[str, str]]  # [{level: int, title: str}]
    entities_detected: List[Entity]
    topics: List[str]
    token_count: int
    content_hash: str
    cross_references: List[str] = []  # other chunk_ids or section refs
    sensitivity_flag: Literal["low", "medium", "high"] = "low"
    embed_text: Optional[str] = None 
