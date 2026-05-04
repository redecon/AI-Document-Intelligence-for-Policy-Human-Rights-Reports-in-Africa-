from typing import Dict


class BudgetGuard:
    """
    Tracks cumulative extraction costs per document and enforces budget caps.
    """

    def __init__(self, max_cost_per_document: float):
        self.max_cost_per_document = max_cost_per_document
        self._ledger: Dict[str, float] = {}

    def track(self, cost_usd: float, document_id: str) -> None:
        """
        Add cost to the running total for a document.
        """
        if document_id not in self._ledger:
            self._ledger[document_id] = 0.0
        self._ledger[document_id] += cost_usd

    def is_exceeded(self, document_id: str) -> bool:
        """
        Return True if cumulative cost exceeds the cap.
        """
        return self._ledger.get(document_id, 0.0) > self.max_cost_per_document

    def reset(self, document_id: str) -> None:
        """
        Clear tracking for a document.
        """
        if document_id in self._ledger:
            del self._ledger[document_id]
