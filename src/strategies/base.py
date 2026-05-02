from abc import ABC, abstractmethod
from typing import Optional

from src.models.document import ExtractedDocument


class BaseExtractor(ABC):
    """
    Abstract base class for all extraction strategies.
    Forces consistency across fast-text, layout, and vision-based extractors.
    """

    @abstractmethod
    def extract(self, pdf_path: str, pages: Optional[list[int]] = None) -> ExtractedDocument:
        """
        Perform extraction on the given PDF.
        Returns a normalized ExtractedDocument.
        """
        pass

    @abstractmethod
    def confidence(self, document: ExtractedDocument) -> float:
        """
        Compute a confidence score (0–1) for the extracted document.
        """
        pass

    @abstractmethod
    def cost_estimate(self, pdf_path: str) -> dict:
        """
        Estimate cost of running this strategy.
        Returns dict with keys:
          - estimated_cost_usd: float
          - method: str (e.g., 'fast_text', 'layout_model', 'vision_model')
        """
        pass
