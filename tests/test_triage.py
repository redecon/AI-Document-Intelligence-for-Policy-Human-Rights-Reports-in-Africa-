import pytest
from pathlib import Path
import json

from src.agents.triage import TriageAgent
from src.models.document import DocumentProfile

DATA_DIR = Path("data/corpus")
REFINERY_DIR = Path(".refinery/profiles")


@pytest.fixture(scope="session")
def triage_agent():
    return TriageAgent()


@pytest.fixture(scope="session")
def profile_english_doc(triage_agent):
    pdf_path = DATA_DIR / "A_HRC_51_46-EN.pdf"
    return triage_agent.profile(str(pdf_path))


@pytest.fixture(scope="session")
def profile_scanned_doc(triage_agent):
    pdf_path = DATA_DIR / "2013-E.C-Audit-finding-information.pdf"
    return triage_agent.profile(str(pdf_path))


@pytest.fixture(scope="session")
def profile_financial_doc(triage_agent):
    pdf_path = DATA_DIR / "tax_expenditure_ethiopia_2021_22.pdf"
    return triage_agent.profile(str(pdf_path))


@pytest.fixture(scope="session")
def profile_human_rights_doc(triage_agent):
    pdf_path = DATA_DIR / "World_Report_2025_Ethiopia_Human-Rights_Watch.pdf"
    return triage_agent.profile(str(pdf_path))


def test_origin_detection_digital(profile_english_doc):
    assert profile_english_doc.origin_type == "native_digital"


def test_origin_detection_scanned(profile_scanned_doc):
    assert profile_scanned_doc.origin_type in ["scanned_image", "mixed"]


def test_language_detection_english(profile_english_doc):
    assert profile_english_doc.primary_language == "en"


def test_domain_hint_financial(profile_financial_doc):
    assert profile_financial_doc.domain_hint == "financial_transparency"


def test_sensitivity_high(profile_human_rights_doc):
    assert profile_human_rights_doc.sensitivity == "high"


def test_profile_save(profile_english_doc):
    file_path = REFINERY_DIR / f"{profile_english_doc.document_id}.json"
    assert file_path.exists()
    data = json.loads(file_path.read_text(encoding="utf-8"))
    assert data["document_id"] == profile_english_doc.document_id
