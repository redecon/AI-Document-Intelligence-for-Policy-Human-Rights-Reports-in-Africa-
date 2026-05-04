import uuid
from typing import List, Dict, Optional
from sentence_transformers import SentenceTransformer
from src.models.chunk import LogicalDocumentUnit
import chromadb


def sanitize_metadata(ldu: LogicalDocumentUnit, chunk_id: str) -> Dict:
    """Ensure metadata values are JSON-friendly for ChromaDB ingestion."""

    def safe_list(val):
        return [str(v) for v in val] if val and len(val) > 0 else None

    metadata = {
        "chunk_id": chunk_id,
        "chunk_type": str(ldu.chunk_type) if ldu.chunk_type else "unknown",
        "sensitivity": str(ldu.sensitivity_flag) if ldu.sensitivity_flag else "low",
    }

    entities = safe_list([getattr(e, "text", e) for e in getattr(ldu, "entities_detected", [])])
    if entities:
        metadata["entities"] = entities

    topics = safe_list(ldu.topics) or ["untagged"]
    metadata["topics"] = topics

    parent_section = safe_list([s["title"] for s in getattr(ldu, "parent_section", []) if isinstance(s, dict)])
    if parent_section:
        metadata["parent_section"] = parent_section

    page_refs = safe_list(ldu.page_refs)
    if page_refs:
        metadata["page_refs"] = page_refs

    return metadata


class VectorStore:
    def __init__(self, persist_dir: str = ".refinery/vector_store",
                 model_name: str = "BAAI/bge-m3"):
        self.client = chromadb.PersistentClient(path=persist_dir)
        self.embedder = SentenceTransformer(model_name)

    def ingest(self, ldus: List[LogicalDocumentUnit], collection_name: str):
        collection = self.client.get_or_create_collection(name=collection_name)

        for ldu in ldus:
            if not ldu.content or not ldu.content.strip():
                print(f"Skipped empty chunk: {ldu.chunk_id}")
                continue

            text = getattr(ldu, "embed_text", None) or ldu.content
            embedding = self.embedder.encode(text)

            chunk_id = str(ldu.chunk_id) if ldu.chunk_id else str(uuid.uuid4())
            metadata = sanitize_metadata(ldu, chunk_id)

            print("Metadata sample:", metadata)

            collection.add(
                ids=[chunk_id],
                embeddings=[embedding],
                metadatas=[metadata],
                documents=[text]
            )

    def search(self, query: str, collection_name: str, top_k: int = 5,
               filters: Optional[Dict] = None) -> List[Dict]:
        collection = self.client.get_collection(name=collection_name)
        query_embedding = self.embedder.encode(query)

        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
            where=filters or {}
        )

        hits = []
        for i in range(len(results["ids"][0])):
            hits.append({
                "chunk_id": results["ids"][0][i],
                "document": results["documents"][0][i],
                "metadata": results["metadatas"][0][i],
                "distance": results["distances"][0][i]
            })
        return hits
