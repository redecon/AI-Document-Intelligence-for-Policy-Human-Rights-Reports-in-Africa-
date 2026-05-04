import time
import json
from pathlib import Path
import yaml

from src.models.document import ExtractedDocument, ExtractionLedgerEntry, DocumentProfile



class ExtractionRouter:
    def __init__(self, fast_text, layout, vision, config_path: str = "rubric/extraction_rules.yaml"):
        # Load externalised config
        with open(config_path, "r", encoding="utf-8") as f:
            self.config = yaml.safe_load(f)

        self.fast_text = fast_text
        self.layout = layout
        self.vision = vision

        self.ledger_path = Path(".refinery/extraction_ledger.jsonl")
        self.ledger_path.parent.mkdir(parents=True, exist_ok=True)

    def extract(
        self,
        pdf_path: str,
        profile: DocumentProfile,
        pages: list[int] | None = None
    ) -> ExtractedDocument:
        start_time = time.time()
        strategy_used = None
        confidence_score = 0.0
        failure_reason = None
        cumulative_cost = 0.0

        # Thresholds from config
        fast_threshold = self.config["strategies"]["fast_text"]["confidence_threshold"]
        layout_threshold = self.config["strategies"]["layout_aware"]["confidence_threshold"]
        vision_threshold = self.config["strategies"]["vision"]["confidence_threshold"]

        # Choose initial strategy based on profile
        if profile.estimated_extraction_cost == "fast_text_sufficient":
            strategy = self.fast_text
            strategy_used = "fast_text"
        elif profile.estimated_extraction_cost == "needs_layout_model":
            strategy = self.layout
            strategy_used = "layout_model"
        else:
            strategy = self.vision
            strategy_used = "vision_model"

        # Run initial extraction
        document = strategy.extract(pdf_path, pages=pages)
        confidence_score = strategy.confidence(document)
        cost_info = strategy.cost_estimate(pdf_path)
        cumulative_cost += cost_info["estimated_cost_usd"]

        # Escalation logic
        if strategy_used == "fast_text" and confidence_score < fast_threshold:
            print("Escalating to layout-aware...")
            strategy = self.layout
            strategy_used = "layout_model"
            document = strategy.extract(pdf_path, pages=pages)
            confidence_score = strategy.confidence(document)
            cost_info = strategy.cost_estimate(pdf_path)
            cumulative_cost += cost_info["estimated_cost_usd"]

        if strategy_used == "layout_model":
            if confidence_score < layout_threshold or profile.origin_type == "low_quality_scan":
                print("Escalating to vision model...")
                strategy = self.vision
                strategy_used = "vision_model"
                document = strategy.extract(pdf_path, pages=pages)
                confidence_score = strategy.confidence(document)
                cost_info = strategy.cost_estimate(pdf_path)
                cumulative_cost += cost_info["estimated_cost_usd"]

        if strategy_used == "vision_model" and confidence_score < vision_threshold:
            failure_reason = "low_confidence_across_all_strategies"

        # Record ledger entry
        processing_time = time.time() - start_time
        ledger_entry = ExtractionLedgerEntry(
            document_id=profile.document_id,
            strategy_used=strategy_used,
            confidence_score=confidence_score,
            cost_estimate={"estimated_cost_usd": cumulative_cost, "method": strategy_used},
            processing_time_sec=processing_time,
            failure_reason=failure_reason,
        )

        with open(self.ledger_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(ledger_entry.dict()) + "\n")

        return document
