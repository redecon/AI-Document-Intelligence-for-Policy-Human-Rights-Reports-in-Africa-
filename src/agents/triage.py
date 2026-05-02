import logging
import hashlib
from pathlib import Path
from collections import Counter

import pdfplumber
import pytesseract
from PIL import Image
import yaml

from src.models.document import DocumentProfile, LanguageInfo
from src.tools.language_detector import LanguageDetector

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


class TriageAgent:
    def _detect_origin_and_layout(self, pdf_path: Path):
        """
        Inspect a PDF and return (origin_type, layout_complexity, data_quality_score).
        Uses heuristics based on text density, image coverage, and table presence.
        """
        with pdfplumber.open(pdf_path) as pdf:
            page_count = len(pdf.pages)
            sample_size = max(int(page_count * 0.2), 5)
            sampled_pages = pdf.pages[:sample_size]

            char_counts, image_ratios, table_counts = [], [], []
            char_density_flags, uniform_text_flags = [], []

            for i, page in enumerate(sampled_pages, start=1):
                text = page.extract_text() or ""
                char_count = len(text)
                char_counts.append(char_count)

                images = page.images
                page_area = page.width * page.height
                total_image_area = sum(img["width"] * img["height"] for img in images)
                image_ratio = total_image_area / page_area if page_area > 0 else 0
                image_ratios.append(image_ratio)

                tables = page.find_tables()
                table_counts.append(len(tables))

                char_density = char_count / page_area if page_area > 0 else 0
                char_density_flags.append(char_density < 0.01)

                uniform_sizes = {char["size"] for char in page.chars} if page.chars else set()
                uniform_text_flags.append(len(uniform_sizes) <= 1 and char_count > 0)

                logger.info(
                    f"Page {i}: chars={char_count}, images={len(images)}, "
                    f"image_ratio={image_ratio:.2f}, tables={len(tables)}, "
                    f"char_density={char_density:.4f}, uniform_text={uniform_text_flags[-1]}"
                )

            avg_char_count = sum(char_counts) / len(char_counts)
            avg_image_ratio = sum(image_ratios) / len(image_ratios)
            avg_tables = sum(table_counts) / len(table_counts)

            if all(c == 0 for c in char_counts):
                origin_type = "scanned_image"
            elif avg_image_ratio > 0.6 and any(char_density_flags):
                origin_type = "low_quality_scan"
            elif any(c == 0 for c in char_counts):
                origin_type = "mixed"
            else:
                origin_type = "native_digital"

            if avg_tables > 2:
                layout_complexity = "table_heavy"
            elif avg_char_count > 0 and avg_char_count / page_area < 0.01:
                layout_complexity = "multi_column"
            elif all(t == 0 for t in table_counts):
                layout_complexity = "single_column"
            else:
                layout_complexity = "mixed"

            score = 100
            if any(char_density_flags):
                score -= 20
            if any(uniform_text_flags):
                score -= 20
            if avg_image_ratio > 0.3:
                score -= 10
            score = max(score, 0)

            return origin_type, layout_complexity, score

    def _civic_classify(self, text: str) -> dict:
        """
        Classify civic intelligence features based on keyword matching.
        """
        keywords_path = Path("rubric/civic_keywords.yaml")
        if not keywords_path.exists():
            raise FileNotFoundError(f"Keyword file not found: {keywords_path}")

        with open(keywords_path, "r", encoding="utf-8") as f:
            keywords = yaml.safe_load(f)

        text_lower = text.lower()
        matched = {k: [] for k in keywords.keys()}
        counts = Counter()

        for category, words in keywords.items():
            for w in words:
                if w.lower() in text_lower:
                    matched[category].append(w)
                    counts[category] += 1

        mapping = {
            "policy": "policy_legislation",
            "financial": "financial_transparency",
            "human_rights": "human_rights",
            "procurement": "procurement_contracts",
            "media": "media_investigative",
            "legal": "policy_legislation",
        }

        priority = ["financial", "human_rights", "procurement", "media", "policy", "legal"]
        domain_hint = "general"
        for domain in priority:
            if counts[domain] > 0:
                domain_hint = mapping[domain]
                break


        if counts["human_rights"] > 0 or counts["corruption"] > 0:
            sensitivity = "high"
        elif counts["financial"] > 0 or counts["procurement"] > 0:
            sensitivity = "medium"
        else:
            sensitivity = "low"

        logger.info(f"Civic classification: domain={domain_hint}, sensitivity={sensitivity}")
        return {
            "domain_hint": domain_hint,
            "sensitivity": sensitivity,
            "corruption_indicators": matched["corruption"],
            "financial_terms": matched["financial"],
            "legal_refs": matched["legal"],
        }

    def profile(self, pdf_path: str) -> DocumentProfile:
        """
        Generate a DocumentProfile for the given PDF.
        """
        pdf_path = Path(pdf_path)
        document_id = hashlib.sha1(pdf_path.name.encode()).hexdigest()[:12]

        try:
            origin_type, layout_complexity, data_quality_score = self._detect_origin_and_layout(pdf_path)
        except Exception as e:
            logger.error(f"Origin/layout detection failed: {e}")
            origin_type, layout_complexity, data_quality_score = "mixed", "mixed", 0.0

        sample_text = ""
        try:
            with pdfplumber.open(pdf_path) as pdf:
                if origin_type == "native_digital":
                    for page in pdf.pages[:5]:
                        sample_text += page.extract_text() or ""
                else:
                    for page in pdf.pages[:2]:
                        im = page.to_image(resolution=200).original
                        sample_text += pytesseract.image_to_string(im)
        except Exception as e:
            logger.warning(f"Text extraction failed: {e}")

        languages, primary_language = [], "unknown"
        try:
            detector = LanguageDetector()
            languages = detector.detect(sample_text[:5000])
            if languages and languages[0].confidence > 0.7:
                primary_language = languages[0].lang_code
            else:
                logger.warning("Low confidence in language detection")
        except Exception as e:
            logger.error(f"Language detection failed: {e}")

        civic = {"domain_hint": "general", "sensitivity": "low",
                 "corruption_indicators": [], "financial_terms": [], "legal_refs": []}
        try:
            civic = self._civic_classify(sample_text)
        except Exception as e:
            logger.error(f"Civic classification failed: {e}")

        if origin_type == "native_digital" and layout_complexity == "single_column":
            estimated_extraction_cost = "fast_text_sufficient"
        elif origin_type in ["scanned_image", "low_quality_scan"]:
            estimated_extraction_cost = "needs_vision_model"
        else:
            estimated_extraction_cost = "needs_layout_model"

        has_toc = False
        try:
            with pdfplumber.open(pdf_path) as pdf:
                for page in pdf.pages[:10]:
                    text = page.extract_text() or ""
                    if "table of contents" in text.lower() or "....." in text:
                        has_toc = True
                        break
        except Exception as e:
            logger.warning(f"TOC detection failed: {e}")

        page_count = 1
        try:
            with pdfplumber.open(pdf_path) as pdf:
                page_count = len(pdf.pages)
        except Exception as e:
            logger.warning(f"Page count detection failed: {e}")

        profile = DocumentProfile(
            document_id=document_id,
            origin_type=origin_type,
            layout_complexity=layout_complexity,
            languages=languages,
            primary_language=primary_language,
            domain_hint=civic["domain_hint"],
            sensitivity=civic["sensitivity"],
            data_quality_score=data_quality_score,
            estimated_extraction_cost=estimated_extraction_cost,
            has_toc=has_toc,
            page_count=page_count,
            corruption_indicators=civic["corruption_indicators"],
            financial_terms=civic["financial_terms"],
            legal_refs=civic["legal_refs"],
        )

        try:
            profile.to_json()
            logger.info(f"Profile saved for {pdf_path.name} → {profile.document_id}")
        except Exception as e:
            logger.error(f"Failed to save profile JSON: {e}")

        return profile
