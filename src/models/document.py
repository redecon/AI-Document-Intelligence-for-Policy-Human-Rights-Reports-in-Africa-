

from typing import List, Literal
from pathlib import Path
import json
from pydantic import BaseModel, Field

from typing import List, Optional
from pydantic import BaseModel, Field


class LanguageInfo(BaseModel):
    """
    Represents a detected language within the document.
    Includes the ISO language code and confidence score.
    """
    lang_code: str = Field(..., description="ISO 639-1 language code (e.g., 'en', 'fr', 'am').")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score between 0.0 and 1.0.")


class DocumentProfile(BaseModel):
    """
    Canonical profile for a civic document.
    This model is the single source of truth for downstream agents.
    """

    document_id: str = Field(..., description="Unique identifier for the document (e.g., filename or UUID).")

    filename: str = Field(..., description="Original filename of the PDF in data/corpus.")

    origin_type: Literal['native_digital', 'scanned_image', 'mixed', 'low_quality_scan'] = Field(
        ..., description="Source type of the document."
    )

    layout_complexity: Literal['single_column', 'multi_column', 'table_heavy', 'form_based', 'mixed'] = Field(
        ..., description="Structural layout complexity of the document."
    )

    languages: List[LanguageInfo] = Field(
        default_factory=list,
        description="List of detected languages with confidence scores."
    )

    primary_language: str = Field(..., description="Primary language code chosen from detected languages.")

    domain_hint: Literal[
        'policy_legislation',
        'financial_transparency',
        'human_rights',
        'procurement_contracts',
        'media_investigative',
        'general'
    ] = Field(..., description="Domain classification hint for the document.")

    sensitivity: Literal['low', 'medium', 'high'] = Field(
        ..., description="Sensitivity level of the document."
    )

    data_quality_score: float = Field(
        ..., ge=0.0, le=100.0,
        description="Composite metric (0–100) of how clean the PDF is."
    )

    estimated_extraction_cost: Literal['fast_text_sufficient', 'needs_layout_model', 'needs_vision_model'] = Field(
        ..., description="Estimated computational cost for extraction."
    )

    has_toc: bool = Field(..., description="Whether the document has a table of contents.")

    page_count: int = Field(..., ge=1, description="Total number of pages in the document.")

    corruption_indicators: List[str] = Field(
        default_factory=list,
        description="Keywords found indicating corruption (e.g., 'irregularity', 'fraud')."
    )

    financial_terms: List[str] = Field(
        default_factory=list,
        description="Financial keywords found in the document."
    )

    legal_refs: List[str] = Field(
        default_factory=list,
        description="Detected references to articles, proclamations, or legal codes."
    )

    def to_json(self, file_path: Path | None = None) -> Path:
        """
        Serialize the profile to JSON.
        Default path: .refinery/profiles/{document_id}.json
        """
        if file_path is None:
            file_path = Path(".refinery/profiles") / f"{self.document_id}.json"
        file_path.parent.mkdir(parents=True, exist_ok=True)

        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(self.model_dump(), f, indent=2, ensure_ascii=False)

        return file_path

class Block(BaseModel):
    type: str  # e.g., 'text', 'table', 'figure'
    bbox: List[float]  # [x0, y0, x1, y1]
    text: Optional[str] = None
    table_json: Optional[dict] = None
    entities: Optional[List[str]] = None


class Page(BaseModel):
    page_number: int
    blocks: List[Block]


class ExtractedDocument(BaseModel):
    document_id: str
    pages: List[Page]


class ExtractionLedgerEntry(BaseModel):
    document_id: str
    strategy_used: str
    confidence_score: float = Field(..., ge=0.0, le=1.0)
    cost_estimate: dict  # {estimated_cost_usd: float, method: str}
    processing_time_sec: float
    failure_reason: Optional[str] = None