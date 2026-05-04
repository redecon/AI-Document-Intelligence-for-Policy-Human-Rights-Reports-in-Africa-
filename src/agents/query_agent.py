from typing import Optional, List, Dict
from langchain.agents import Tool
from langgraph.graph import StateGraph
from pydantic import BaseModel

from src.models.query import QueryAnswer, ProvenanceCitation, TruthClassification
from src.tools.vector_store import VectorStore
from src.agents.indexer import PageIndexBuilder
from src.tools.fact_table import FactTableBuilder

import sqlite3


# --- Tool implementations ---

def pageindex_navigate(query: str) -> dict:
    """Search PageIndex tree for relevant sections."""
    builder = PageIndexBuilder()
    results = builder.search_by_topic(query)
    return {"sections": results[:3]}  # top-3


def semantic_search(query: str, section_filter: Optional[List[str]] = None) -> List[dict]:
    """Query ChromaDB vector store with optional section filter."""
    vs = VectorStore()
    filters = {"parent_section": {"$in": section_filter}} if section_filter else None
    return vs.search(query, collection_name="phase3_chunks", top_k=5, filters=filters)


def structured_query(sql: str) -> List[dict]:
    """Execute read-only SQL query against FactTable database."""
    conn = sqlite3.connect(".refinery/fact_table.db")
    cur = conn.cursor()
    cur.execute(sql)
    rows = cur.fetchall()
    cols = [desc[0] for desc in cur.description]
    conn.close()
    return [dict(zip(cols, row)) for row in rows]


# --- Agent definition ---

class QueryAgent:
    def __init__(self, llm):
        # Define tools as LangChain Tools
        self.tools = [
            Tool(name="pageindex_navigate", func=pageindex_navigate, description="Navigate PageIndex tree"),
            Tool(name="semantic_search", func=semantic_search, description="Semantic search over vector store"),
            Tool(name="structured_query", func=structured_query, description="Run SQL query over FactTable"),
        ]
        self.llm = llm

        # Build LangGraph orchestration
        self.graph = StateGraph()
        for tool in self.tools:
            self.graph.add_node(tool.name, tool.func)

        # Define orchestration edges (LLM decides which tool to call)
        self.graph.add_edge("start", "pageindex_navigate")
        self.graph.add_edge("pageindex_navigate", "semantic_search")
        self.graph.add_edge("semantic_search", "structured_query")
        self.graph.add_edge("structured_query", "end")

    def answer(self, question: str) -> QueryAnswer:
        """
        Run the agent: decide which tools to call, gather results,
        and synthesize a provenance-backed QueryAnswer.
        """
        # System prompt with safety guard
        system_prompt = (
            "You are a civic accountability agent. You have three tools: "
            "pageindex_navigate, semantic_search, structured_query. "
            "Every answer must be backed by provenance citations. "
            "If information is not present, state that clearly and mark UNVERIFIED. "
            "Never fabricate information."
        )

        # LLM reasoning step
        reasoning = self.llm.predict(system_prompt + "\nQuestion: " + question)

        # Example orchestration: navigate → semantic search → maybe structured query
        sections = pageindex_navigate(question)["sections"]
        chunks = semantic_search(question, section_filter=[s["title"] for s in sections])
        sql_results = []
        if any(kw in question.lower() for kw in ["budget", "expenditure", "amount", "allocation"]):
            # Generate SQL query via LLM
            sql_query = self.llm.predict("Generate SQL for: " + question)
            sql_results = structured_query(sql_query)

        # Synthesize answer
        if chunks or sql_results:
            answer_text = self.llm.predict("Synthesize answer from chunks and SQL results")
            citations = []
            for ch in chunks:
                citations.append(ProvenanceCitation(
                    document_name=ch["metadata"].get("document_name", "unknown"),
                    page_number=int