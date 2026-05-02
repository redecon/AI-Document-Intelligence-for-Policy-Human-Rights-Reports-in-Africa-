# tests/test_document.py
import sys, pathlib
import json
from pathlib import Path
import pytest
from src.models.document import DocumentProfile, LanguageInfo

sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))


def test_document_profile_creation(tmp_path: Path):
    # Create a sample profile
    profile = DocumentProfile(
        document_id="audit_2023",
        origin_type="scanned_image",
        layout_complexity="multi_column",
        languages=[LanguageInfo(lang_code="en", confidence=0.95)],
        primary_language="en",
        domain_hint="financial_transparency",
        sensitivity="high",
        data_quality_score=72.5,
        estimated_extraction_cost="needs_layout_model",
        has_toc=False,
        page_count=95,
        corruption_indicators=["fraud", "irregularity"],
        financial_terms=["balance sheet", "expenditure"],
        legal_refs=["Proclamation 123/2004", "Article 5"]
    )

    # Serialize to JSON
    file_path = profile.to_json(tmp_path / "audit_2023.json")

    # Verify file exists
    assert file_path.exists()

    # Load back and check fields
    data = json.loads(file_path.read_text(encoding="utf-8"))
    assert data["document_id"] == "audit_2023"
    assert data["primary_language"] == "en"
    assert "fraud" in data["corruption_indicators"]
    assert data["page_count"] == 95


def test_language_info_confidence_bounds():
    # Confidence must be between 0 and 1
    with pytest.raises(ValueError):
        LanguageInfo(lang_code="en", confidence=1.5)
