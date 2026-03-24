from pydantic import BaseModel
from typing import Any, Optional


class GraphNode(BaseModel):
    id: str                      # "SalesOrder:12345"
    entity_type: str
    entity_id: str
    label: str
    properties: dict[str, Any]


class GraphEdge(BaseModel):
    source: str                  # node composite id
    target: str                  # node composite id
    relationship: str


class GraphResponse(BaseModel):
    nodes: list[GraphNode]
    edges: list[GraphEdge]


class GraphStats(BaseModel):
    total_nodes: int
    total_edges: int
    by_entity_type: dict[str, int]
    by_relationship: dict[str, int]
