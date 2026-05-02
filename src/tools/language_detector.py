# src/tools/language_detector.py

import logging
from pathlib import Path
from typing import List
import fasttext
from src.models.document import LanguageInfo

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

class LanguageDetector:
    """
    Wrapper around fastText language ID model (lid.176.bin).
    Provides single-text and batch detection methods.
    """

    def __init__(self, model_path: Path | None = None):
        if model_path is None:
            # Default location: docs/phase0 or models/
            model_path = Path("docs/phase0/lid.176.bin")
            if not model_path.exists():
                model_path = Path("models/lid.176.bin")

        if not model_path.exists():
            raise FileNotFoundError(f"FastText model not found at {model_path}")

        self.ft_model = fasttext.load_model(str(model_path))
        logger.info(f"Loaded FastText model from {model_path}")

    def detect(self, text: str) -> List[LanguageInfo]:
        """
        Detect top-3 languages from a text string.
        Returns list of LanguageInfo objects.
        """
        if not text.strip():
            return []

        preds = self.ft_model.predict(text.replace("\n", " "), k=3)
        labels = [lbl.replace("__label__", "") for lbl in preds[0]]
        scores = preds[1]

        results = [
            LanguageInfo(lang_code=lbl, confidence=float(score))
            for lbl, score in zip(labels, scores)
        ]

        for r in results:
            logger.info(f"Detected {r.lang_code} with confidence {r.confidence:.3f}")

        return results

    def detect_from_pages(self, pages_text: List[str]) -> List[LanguageInfo]:
        """
        Aggregate language detection across multiple pages.
        Returns dominant languages with averaged confidence.
        """
        all_results = []
        for text in pages_text:
            all_results.extend(self.detect(text))

        if not all_results:
            return []

        # Aggregate by language code
        agg = {}
        for r in all_results:
            agg.setdefault(r.lang_code, []).append(r.confidence)

        aggregated = [
            LanguageInfo(lang_code=lang, confidence=sum(scores) / len(scores))
            for lang, scores in agg.items()
        ]

        # Sort by confidence descending
        aggregated.sort(key=lambda x: x.confidence, reverse=True)

        return aggregated
