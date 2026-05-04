import json
import pickle
from pathlib import Path
import statistics

from src.models.document import ExtractedDocument
from src.models.chunk import LogicalDocumentUnit
from src.agents.chunker import ChunkingEngine
from src.agents.indexer import PageIndexBuilder
from src.tools.vector_store import VectorStore


extractions_dir = Path(".refinery/extractions")
chunks_dir = Path(".refinery/chunks")
pageindex_dir = Path(".refinery/pageindex")

chunks_dir.mkdir(parents=True, exist_ok=True)
pageindex_dir.mkdir(parents=True, exist_ok=True)


def load_extractions():
    docs = []
    for f in extractions_dir.glob("*.json"):
        with open(f, "r", encoding="utf-8") as ef:
            data = json.load(ef)
            docs.append(ExtractedDocument(**data))
    return docs


def main():
    chunker = ChunkingEngine()
    indexer = PageIndexBuilder()
    vs = VectorStore()

    all_ldus = []
    token_counts = []
    entity_counter = {}
    topic_counter = {}

    documents = load_extractions()
    for doc in documents:
        print(f"\nProcessing {doc.document_id}...")

        # Chunking
        ldus = chunker.chunk(doc)
        for ldu in ldus:
            token_counts.append(ldu.token_count)
            for e in ldu.entities_detected:
                entity_counter[e.text] = entity_counter.get(e.text, 0) + 1
            for t in ldu.topics:
                topic_counter[t] = topic_counter.get(t, 0) + 1

        # Save LDUs
        out_json = chunks_dir / f"{doc.document_id}.json"
        with open(out_json, "w", encoding="utf-8") as f:
            f.write(json.dumps([ldu.model_dump() for ldu in ldus], indent=2))

        # PageIndex
        tree = indexer.build(doc, ldus)

        # Save PageIndex
        out_json = pageindex_dir / f"{doc.document_id}.json"
        with open(out_json, "w", encoding="utf-8") as f:
            f.write(tree.model_dump_json(indent=2))

        # Ingest into vector store
        vs.ingest(ldus, collection_name="phase3_chunks")

        all_ldus.extend(ldus)

    # Summary stats
    print("\n=== Phase 3 Summary ===")
    print(f"Total chunks: {len(all_ldus)}")
    print(f"Average tokens per chunk: {statistics.mean(token_counts):.2f}")
    print(f"Entity coverage: {len(entity_counter)} unique entities")
    print(f"Topic distribution: {topic_counter}")


if __name__ == "__main__":
    main()
