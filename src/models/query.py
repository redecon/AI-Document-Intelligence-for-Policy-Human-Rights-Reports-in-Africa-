from typing import List, Tuple, Literal, Optional
from pydantic import BaseModel, Field


class ProvenanceCitation(BaseModel):
    """Pin every claim to its source with verifiable evidence."""
    document_name: str = Field(..., description="Name of the source document")
    page_number: int = Field(..., description="Page number in the document")
    bbox: Tuple[float, float, float, float] = Field(
        ..., description="Bounding box coordinates (x0, y0, x1, y1)"
    )
    exact_quote: str = Field(..., description="Exact text snippet from the source")
    content_hash: str = Field(..., description="Hash of the source content for integrity")


TruthClassification = Literal["VERIFIED", "INFERRED", "UNVERIFIED"]


class QueryAnswer(BaseModel):
    """Structured answer contract for civic queries."""
    question: str = Field(..., description="The user’s question")
    answer: str = Field(..., description="The system’s answer")
    classification: TruthClassification = Field(
        ..., description="Truth label: VERIFIED, INFERRED, or UNVERIFIED"
    )
    citations: List[ProvenanceCitation] = Field(
        ..., description="List of provenance citations backing the answer"
    )
    confidence: float = Field(..., description="Overall retrieval confidence score")
    thinking: str = Field(
        ..., description="LLM reasoning trace for auditability"
    )


class StructuredFact(BaseModel):
    """Represents a numerical fact extracted into the FactTable for SQL querying."""


class StructuredFact(BaseModel):
    fact_id: str
    document_id: str
    page: int
    fact_type: str
    value: float
    unit: Optional[str] = None   
    year: Optional[int] = None   
    description: str
    provenance: ProvenanceCitation

