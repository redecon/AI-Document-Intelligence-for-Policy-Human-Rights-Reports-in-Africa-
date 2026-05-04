from typing import List
from pydantic import BaseModel

class PageIndexNode(BaseModel):
    node_id: str
    title: str
    start_page: int
    end_page: int
    summary: str
    key_entities: List[str]
    topics: List[str]
    data_types_present: List[str]  # e.g., ["tables", "figures"]
    children: List["PageIndexNode"] = []

class PageIndexTree(BaseModel):
    document_id: str
    doc_name: str
    root_nodes: List[PageIndexNode]

#Note: For recursive models like PageIndexNode.children, we’ll need to call PageIndexNode.update_forward_refs() at the bottom of the file.