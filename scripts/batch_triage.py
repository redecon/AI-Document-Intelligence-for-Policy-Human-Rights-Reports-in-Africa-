# scripts/batch_triage.py

import logging
import csv
from pathlib import Path

from src.agents.triage import TriageAgent

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

DATA_DIR = Path("data/corpus")
OUTPUT_DIR = Path(".refinery/profiles")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
SUMMARY_PATH = OUTPUT_DIR / "profiles_summary.csv"


def main():
    agent = TriageAgent()
    profiles = []
    errors = []

    for pdf_file in DATA_DIR.glob("*.pdf"):
        try:
            logger.info(f"Profiling {pdf_file.name}...")
            profile = agent.profile(str(pdf_file))
            profiles.append(profile)
        except Exception as e:
            logger.error(f"Failed to profile {pdf_file.name}: {e}")
            errors.append((pdf_file.name, str(e)))

    # Summarize results
    sensitivity_counts = {"high": 0, "medium": 0, "low": 0}
    domain_counts = {}

    for p in profiles:
        sensitivity_counts[p.sensitivity] = sensitivity_counts.get(p.sensitivity, 0) + 1
        domain_counts[p.domain_hint] = domain_counts.get(p.domain_hint, 0) + 1

    logger.info("=== Summary ===")
    logger.info(f"Total profiles: {len(profiles)}")
    logger.info(f"Sensitivity counts: {sensitivity_counts}")
    logger.info(f"Domain distribution: {domain_counts}")
    if errors:
        logger.warning(f"{len(errors)} errors encountered")

    # Save summary CSV
    with open(SUMMARY_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "document_id", "filename", "origin_type", "layout_complexity",
            "primary_language", "domain_hint", "sensitivity", "page_count"
        ])
        for p in profiles:
            writer.writerow([
                p.document_id,
                p.document_id + ".pdf",  # or use actual filename if you store it
                p.origin_type,
                p.layout_complexity,
                p.primary_language,
                p.domain_hint,
                p.sensitivity,
                p.page_count,
            ])

    logger.info(f"Summary saved to {SUMMARY_PATH}")


if __name__ == "__main__":
    main()
