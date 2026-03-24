from fastapi import APIRouter, HTTPException, Query
from typing import Optional

from database.connection import Database
from graph import service as svc
from graph.models import GraphResponse, GraphStats

router = APIRouter(prefix="/api/graph", tags=["graph"])


@router.get("/overview", response_model=GraphResponse)
def graph_overview(limit: int = Query(default=250, le=500)):
    """Sampled subgraph for initial visualization."""
    db = Database.get()
    return svc.get_overview(db, limit=limit)


@router.get("/stats", response_model=GraphStats)
def graph_stats():
    """Counts per entity type and relationship type."""
    db = Database.get()
    return svc.get_stats(db)


@router.get("/node/{entity_type}/{entity_id}")
def node_detail(entity_type: str, entity_id: str):
    """Full node metadata."""
    db = Database.get()
    node = svc.get_node(db, entity_type, entity_id)
    if node is None:
        raise HTTPException(status_code=404, detail=f"Node {entity_type}:{entity_id} not found")
    return node


@router.get("/neighbors/{entity_type}/{entity_id}", response_model=GraphResponse)
def node_neighbors(entity_type: str, entity_id: str):
    """1-hop neighbours — called when user clicks to expand a node."""
    db = Database.get()
    return svc.get_neighbors(db, entity_type, entity_id)


@router.get("/trace/{entity_type}/{entity_id}", response_model=GraphResponse)
def trace_flow(entity_type: str, entity_id: str, depth: int = Query(default=8, le=12)):
    """Full Order-to-Cash flow for the given entity (BFS traversal)."""
    db = Database.get()
    return svc.trace_flow(db, entity_type, entity_id, max_depth=depth)


@router.get("/filter", response_model=GraphResponse)
def filter_graph(
    types: Optional[str] = Query(default=None, description="Comma-separated entity types"),
    limit: int = Query(default=100, le=500),
):
    """Filter nodes by entity type."""
    db = Database.get()
    entity_types = [t.strip() for t in types.split(",")] if types else None
    return svc.filter_graph(db, entity_types=entity_types, limit=limit)
