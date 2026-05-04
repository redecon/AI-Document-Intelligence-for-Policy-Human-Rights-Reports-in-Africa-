import json
import pickle
import time
from pathlib import Path
from sympy import re
import yaml

from src.strategies.fast_text import FastTextExtractor
from src.strategies.layout_aware import LayoutExtractor
from src.strategies.vision_model import VisionExtractor
from src.agents.extractor import ExtractionRouter
from src.models.document import DocumentProfile
from src.models.document import ExtractedDocument

import re

# Paths
profiles_dir = Path(".refinery/profiles")
extractions_dir = Path(".refinery/extractions")
ledger_path = Path(".refinery/extraction_ledger.jsonl")

extractions_dir.mkdir(parents=True, exist_ok=True)

BATCH_SIZE = 20  # number of pages per run


def safe_id(name: str) -> str:
    # Replace spaces and non-alphanumeric characters with underscores
    return re.sub(r'[^A-Za-z0-9]+', '_', name).strip('_')


def load_profiles():
    profiles = []
    for f in profiles_dir.glob("*.json"):
        with open(f, "r", encoding="utf-8") as pf:
            data = json.load(pf)
            profiles.append(DocumentProfile(**data))
    return profiles

def main():
    # Load config
    with open("rubric/extraction_rules.yaml", "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    fast_text = FastTextExtractor()
    layout = LayoutExtractor()
    vision = VisionExtractor()
    router = ExtractionRouter(fast_text, layout, vision, config_path="rubric/extraction_rules.yaml")

    total_cost = 0.0
    escalations = 0
    budget_caps = []

    MAX_LAYOUT_PAGES = 40  # threshold for safe Docling use

    profiles = load_profiles()
    for profile in profiles:
        pdf_path = Path("data/corpus") / profile.filename
        print(f"\nProcessing {profile.filename}...")

        total_pages = profile.page_count
        batch_documents = []
        elapsed_total = 0.0

        # Run batches
        for start_page in range(1, total_pages + 1, BATCH_SIZE):
            end_page = min(start_page + BATCH_SIZE - 1, total_pages)
            page_range = list(range(start_page, end_page + 1))

            print(f"  Extracting pages {start_page}-{end_page}...")
            start = time.time()

            # Decide strategy based on page count
            if profile.page_count <= MAX_LAYOUT_PAGES:
                chosen_strategy = "layout_model"
                document = layout.extract(str(pdf_path), pages=page_range)
            elif profile.page_count <= 100:
                chosen_strategy = "vision_model"
                document = vision.extract(str(pdf_path), pages=page_range)
            else:
                chosen_strategy = "fast_text"
                document = fast_text.extract(str(pdf_path), pages=page_range)

            elapsed = time.time() - start
            elapsed_total += elapsed
            batch_documents.append(document)
            print(f"    Batch {start_page}-{end_page} done in {elapsed:.2f}s")

        # Merge batches
        merged_pages = []
        for doc in batch_documents:
            merged_pages.extend(doc.pages)

        merged_document = ExtractedDocument(
            document_id=profile.document_id,
            pages=merged_pages
        )

        # Save merged outputs
        safe_name = safe_id(profile.filename)
        out_json = extractions_dir / f"{profile.document_id}_{safe_name}.json"
        with open(out_json, "w", encoding="utf-8") as f:
            f.write(merged_document.model_dump_json())

        out_pkl = extractions_dir / f"{profile.document_id}_{safe_name}.pkl"
        with open(out_pkl, "wb") as f:
            pickle.dump(merged_document, f)

        # Write merged ledger entry with chosen strategy
        ledger_entry = {
            "document_id": profile.document_id,
            "strategy_used": chosen_strategy,
            "confidence_score": layout.confidence(merged_document),
            "cost_estimate": layout.cost_estimate(str(pdf_path)),
            "processing_time_sec": elapsed_total,
            "failure_reason": None,
        }
        with open(ledger_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(ledger_entry) + "\n")

        # Update totals
        total_cost += ledger_entry["cost_estimate"]["estimated_cost_usd"]
        if ledger_entry["failure_reason"] == "budget_capped":
            budget_caps.append(profile.document_id)
        if chosen_strategy != profile.estimated_extraction_cost:
            escalations += 1

        print(f"  [Merged] Strategy: {chosen_strategy} | "
              f"Confidence: {ledger_entry['confidence_score']:.2f} | "
              f"Cost: ${ledger_entry['cost_estimate']['estimated_cost_usd']:.4f} | "
              f"Time: {elapsed_total:.2f}s | "
              f"Failure: {ledger_entry['failure_reason']}")

    # Final report
    print("\n=== Extraction Report ===")
    print(f"Total documents processed: {len(profiles)}")
    print(f"Total cost: ${total_cost:.4f}")
    print(f"Escalations: {escalations}")
    if budget_caps:
        print(f"Documents hitting budget cap: {', '.join(budget_caps)}")
    else:
        print("No documents hit budget cap.")
if __name__ == "__main__":
    main()