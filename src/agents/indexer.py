import json
from pathlib import Path
from typing import List
import yaml
from collections import Counter

from src.models.pageindex import PageIndexTree, PageIndexNode
from src.models.chunk import LogicalDocumentUnit
from src.models.document import ExtractedDocument


class PageIndexBuilder:
    def __init__(self, config_path: str = "rubric/chunking_rules.yaml"):
        with open(config_path, "r", encoding="utf-8") as f:
            self.rules = yaml.safe_load(f)["rules"]

    def build(self, document: ExtractedDocument, ldus: List[LogicalDocumentUnit]) -> PageIndexTree:
        root_nodes = []

        # Step 1: Extract section hierarchy
        section_map = self._group_by_section(ldus)

        for section_title, section_ldus in section_map.items():
            start_page = min(min(ldu.page_refs) for ldu in section_ldus)
            end_page = max(max(ldu.page_refs) for ldu in section_ldus)

            # Step 2: Aggregate entities and topics
            entities = [ent.text for ldu in section_ldus for ent in ldu.entities_detected]
            topics = [t for ldu in section_ldus for t in ldu.topics]
            key_entities = [e for e, _ in Counter(entities).most_common(5)]
            unique_topics = list(set(topics))

            # Step 3: Detect data types
            data_types = set()
            for ldu in section_ldus:
                if ldu.chunk_type == "table":
                    data_types.add("tables")
                if ldu.chunk_type == "figure":
                    data_types.add("figures")
                if ldu.chunk_type == "legal_clause":
                    data_types.add("legal_references")

            # Step 4: Generate summaries
            summary = self._summarize_section(section_ldus)

            node = PageIndexNode(
                node_id=f"{document.document_id}_{section_title.replace(' ', '_')}",
                title=section_title,
                start_page=start_page,
                end_page=end_page,
                summary=summary,
                key_entities=key_entities,
                topics=unique_topics,
                data_types_present=list(data_types),
                children=[]
            )
            root_nodes.append(node)

        tree = PageIndexTree(
            document_id=document.document_id,
            doc_name=getattr(document, "doc_name", document.document_id),
            root_nodes=root_nodes
        )

        # Step 5: Save tree
        out_path = Path(".refinery/pageindex") / f"{document.document_id}.json"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(tree.model_dump_json(indent=2))

        return tree

    def search_by_topic(self, tree: PageIndexTree, topic: str) -> List[str]:
        matches = []

        def traverse(node: PageIndexNode):
            if topic in node.topics:
                matches.append(node.node_id)
            for child in node.children:
                traverse(child)

        for root in tree.root_nodes:
            traverse(root)
        return matches

    def _group_by_section(self, ldus: List[LogicalDocumentUnit]):
        section_map = {}
        for ldu in ldus:
            section_title = " > ".join([s["title"] for s in ldu.parent_section]) if ldu.parent_section else "root"
            section_map.setdefault(section_title, []).append(ldu)
        return section_map

    def _summarize_section(self, ldus: List[LogicalDocumentUnit]) -> str:
        # Placeholder: call LLM or heuristic summarizer
        text = " ".join(ldu.content for ldu in ldus[:3])  # sample first few chunks
        return f"Summary of section: {text[:200]}..."
