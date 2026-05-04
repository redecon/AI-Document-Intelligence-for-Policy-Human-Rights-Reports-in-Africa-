import csv
from pathlib import Path
from typing import List, Dict

from src.tools.vector_store import VectorStore
from src.agents.indexer import PageIndexBuilder
from src.models.chunk import LogicalDocumentUnit
from src.models.document import ExtractedDocument

# Ground truth: 10 sample Q&A pairs for CBE Annual Report
GROUND_TRUTH = [
    {
        "query": "What was the total profit for FY2023-24?",
        "answer_page": 15,
        "answer_section": "Financial Results",
    },
    {
        "query": "Which proclamation governs procurement?",
        "answer_page": 42,
        "answer_section": "Legal References",
    },
    # ... add 8 more manually curated questions
]

def precision_at_k(results: List[Dict], ground_truth: Dict, k: int = 5) -> float:
    correct = 0
    for r in results[:k]:
        if ground_truth["answer_section"] in r["metadata"].get("parent_section", []) \
           or ground_truth["answer_page"] in r["metadata"].get("page_refs", []):
            correct += 1
    return correct / k

def reciprocal_rank(results: List[Dict], ground_truth: Dict) -> float:
    for i, r in enumerate(results):
        if ground_truth["answer_section"] in r["metadata"].get("parent_section", []) \
           or ground_truth["answer_page"] in r["metadata"].get("page_refs", []):
            return 1.0 / (i + 1)
    return 0.0

def evaluate(document: ExtractedDocument, ldus: List[LogicalDocumentUnit], collection_name: str):
    vs = VectorStore()
    vs.ingest(ldus, collection_name)

    # Build PageIndex
    builder = PageIndexBuilder()
    tree = builder.build(document, ldus)

    results = []
    for gt in GROUND_TRUTH:
        query = gt["query"]

        # a. Baseline: naive vector search over raw 512-token chunks
        baseline_hits = vs.search(query, collection_name, top_k=5)

        # b. LDU-based: vector search with metadata filtering
        ldu_hits = vs.search(query, collection_name, top_k=5,
                             filters={"topics": {"$contains": gt["answer_section"]}})

        # c. PageIndex-guided: restrict to relevant sections
        section_nodes = builder.search_by_topic(tree, gt["answer_section"])
        section_hits = []
        for node_id in section_nodes:
            section_hits.extend(vs.search(query, collection_name, top_k=5,
                                          filters={"parent_section": {"$contains": node_id}}))

        # Metrics
        baseline_p5 = precision_at_k(baseline_hits, gt)
        ldu_p5 = precision_at_k(ldu_hits, gt)
        pageindex_p5 = precision_at_k(section_hits, gt)

        baseline_rr = reciprocal_rank(baseline_hits, gt)
        ldu_rr = reciprocal_rank(ldu_hits, gt)
        pageindex_rr = reciprocal_rank(section_hits, gt)

        results.append({
            "query": query,
            "baseline_p5": baseline_p5,
            "ldu_p5": ldu_p5,
            "pageindex_p5": pageindex_p5,
            "baseline_rr": baseline_rr,
            "ldu_rr": ldu_rr,
            "pageindex_rr": pageindex_rr,
        })

    # Save results
    out_path = Path("docs/phase3/retrieval_evaluation.csv")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=results[0].keys())
        writer.writeheader()
        writer.writerows(results)

    # Print comparison table
    print("\n=== Retrieval Evaluation ===")
    print(f"{'Query':40} | Baseline P@5 | LDU P@5 | PageIndex P@5 | Baseline RR | LDU RR | PageIndex RR")
    for r in results:
        print(f"{r['query'][:40]:40} | {r['baseline_p5']:.2f}        | {r['ldu_p5']:.2f}    | {r['pageindex_p5']:.2f}       | "
              f"{r['baseline_rr']:.2f}       | {r['ldu_rr']:.2f}   | {r['pageindex_rr']:.2f}")
