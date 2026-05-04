import json
import pickle
import time
from pathlib import Path
import yaml

from src.strategies.fast_text import FastTextExtractor
from src.strategies.layout_aware import LayoutExtractor
from src.strategies.vision_model import VisionExtractor
from src.agents.extractor import ExtractionRouter
from src.models.document import DocumentProfile

# Paths
profiles_dir = Path(".refinery/profiles")
extractions_dir = Path(".refinery/extractions")
ledger_path = Path(".refinery/extraction_ledger.jsonl")

extractions_dir.mkdir(parents=True, exist_ok=True)

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

    # Instantiate strategies
    fast_text = FastTextExtractor()
    layout = LayoutExtractor()
    vision = VisionExtractor()

    # Router
    router = ExtractionRouter(fast_text, layout, vision, config_path="rubric/extraction_rules.yaml")

    total_cost = 0.0
    escalations = 0
    budget_caps = []

    profiles = load_profiles()
    for profile in profiles:
        pdf_path = Path("data/corpus") / f"{profile.document_id}.pdf"
        print(f"\nProcessing {profile.document_id}...")

        start = time.time()
        document = router.extract(str(pdf_path), profile)
        elapsed = time.time() - start

        # Save extraction
        out_json = extractions_dir / f"{profile.document_id}.json"
        with open(out_json, "w", encoding="utf-8") as f:
            f.write(document.json())

        # Also save pickle if needed
        out_pkl = extractions_dir / f"{profile.document_id}.pkl"
        with open(out_pkl, "wb") as f:
            pickle.dump(document, f)

        # Read last ledger entry for summary
        with open(ledger_path, "r", encoding="utf-8") as lf:
            last_line = list(lf)[-1]
            entry = json.loads(last_line)

        total_cost += entry["cost_estimate"]["estimated_cost_usd"]
        if entry.get("failure_reason") == "budget_capped":
            budget_caps.append(profile.document_id)
        if entry["strategy_used"] != profile.estimated_extraction_cost:
            escalations += 1

        print(f"  Strategy: {entry['strategy_used']} | "
              f"Confidence: {entry['confidence_score']:.2f} | "
              f"Cost: ${entry['cost_estimate']['estimated_cost_usd']:.4f} | "
              f"Time: {elapsed:.2f}s | "
              f"Failure: {entry.get('failure_reason')}")

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
