from typing import List, Dict
import sqlite3
import uuid
from src.models.query import ProvenanceCitation
from src.tools.vector_store import VectorStore
from src.agents.indexer import PageIndexBuilder
from src.tools.fact_table import FactTableBuilder


class AuditMode:
    def __init__(self, llm):
        self.llm = llm
        self.vs = VectorStore()
        self.pageindex = PageIndexBuilder()
        self.fact_table = FactTableBuilder()

    def verify(self, claim: str) -> Dict:
        """
        Verify a raw claim against the document corpus.
        Returns dict with status, citations, and explanation/message.
        """

        # Step 1: Convert claim into search query
        query = claim

        # Step 2: Identify relevant sections
        sections = self.pageindex.search_by_topic(query)

        # Step 3: Semantic search
        chunks = self.vs.search(query, collection_name="phase3_chunks", top_k=5,
                                filters={"parent_section": {"$in": [s["title"] for s in sections]}})

        # Step 4: Structured query for numerical claims
        sql_results = []
        if any(kw in claim.lower() for kw in ["budget", "expenditure", "allocation", "amount", "fy", "year"]):
            # Generate SQL query via LLM
            sql_query = self.llm.predict("Generate SQL for claim: " + claim)
            try:
                conn = sqlite3.connect(".refinery/fact_table.db")
                cur = conn.cursor()
                cur.execute(sql_query)
                rows = cur.fetchall()
                cols = [desc[0] for desc in cur.description]
                sql_results = [dict(zip(cols, row)) for row in rows]
                conn.close()
            except Exception:
                sql_results = []

        # Step 5: Entailment check
        supporting_citations: List[ProvenanceCitation] = []
        explanation = ""
        for ch in chunks:
            entailment_prompt = (
                f"Does the following text support, refute, or not mention this claim?\n"
                f"Claim: {claim}\nText: {ch['document']}"
            )
            verdict = self.llm.predict(entailment_prompt)
            if "support" in verdict.lower():
                citation = ProvenanceCitation(
                    document_name=ch["metadata"].get("document_name", "unknown"),
                    page_number=int(ch["metadata"].get("page_refs", [0])[0]),
                    bbox=(0.0, 0.0, 0.0, 0.0),  # placeholder until bbox is available
                    exact_quote=ch["document"][:200],
                    content_hash=ch["metadata"].get("content_hash", "")
                )
                supporting_citations.append(citation)
                explanation = f"Claim supported by chunk on page {citation.page_number}."

        # Step 6: Strict verification
        if supporting_citations:
            return {
                "status": "VERIFIED",
                "citations": [c.dict() for c in supporting_citations],
                "explanation": explanation
            }
        elif sql_results:
            return {
                "status": "INFERRED",
                "citations": sql_results,
                "explanation": "Claim inferred from structured financial data; direct textual support not found."
            }
        else:
            return {
                "status": "UNVERIFIED",
                "message": "No supporting evidence found in the document."
            }
