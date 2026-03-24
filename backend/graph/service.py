"""
Graph service — query the graph_nodes / graph_edges tables and return
structured GraphNode / GraphEdge objects.
"""

import json
import logging
from typing import Any

from graph.models import GraphEdge, GraphNode, GraphResponse, GraphStats

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_node_id(entity_type: str, entity_id: str) -> str:
    return f"{entity_type}:{entity_id}"


def _row_to_node(row) -> GraphNode:
    """Convert a DB row (entity_type, entity_id, label, properties) to GraphNode."""
    entity_type, entity_id, label, properties_raw = row
    if isinstance(properties_raw, str):
        try:
            properties = json.loads(properties_raw)
        except Exception:
            properties = {}
    elif isinstance(properties_raw, dict):
        properties = properties_raw
    else:
        properties = {}

    return GraphNode(
        id=_make_node_id(entity_type, entity_id),
        entity_type=entity_type,
        entity_id=str(entity_id),
        label=label or f"{entity_type}:{entity_id}",
        properties=properties,
    )


def _row_to_edge(row) -> GraphEdge:
    """Convert a DB row (source_type, source_id, target_type, target_id, relationship)."""
    source_type, source_id, target_type, target_id, relationship = row
    return GraphEdge(
        source=_make_node_id(source_type, source_id),
        target=_make_node_id(target_type, target_id),
        relationship=relationship,
    )


# ---------------------------------------------------------------------------
# Public service functions
# ---------------------------------------------------------------------------

def get_overview(db, limit: int = 250) -> GraphResponse:
    """
    Return a sampled subgraph for initial visualization.
    Strategy: pick up to `sample_orders` SalesOrders then expand their
    full O2C flow via BFS through graph_edges.
    """
    sample_orders = 30

    # Step 1: pick a sample of SalesOrder node IDs
    seed_rows = db.execute(f"""
        SELECT entity_id FROM graph_nodes
        WHERE entity_type = 'SalesOrder'
        LIMIT {sample_orders}
    """).fetchall()
    seed_ids = [r[0] for r in seed_rows]

    if not seed_ids:
        # Fallback: just return whatever nodes exist
        node_rows = db.execute(
            f"SELECT entity_type, entity_id, label, properties FROM graph_nodes LIMIT {limit}"
        ).fetchall()
        edge_rows = db.execute(
            f"SELECT source_type, source_id, target_type, target_id, relationship FROM graph_edges LIMIT {limit}"
        ).fetchall()
        return GraphResponse(
            nodes=[_row_to_node(r) for r in node_rows],
            edges=[_row_to_edge(r) for r in edge_rows],
        )

    # Step 2: BFS from seeds through graph_edges up to 3 hops
    visited_type_ids: set[tuple[str, str]] = set()
    frontier: list[tuple[str, str]] = [("SalesOrder", sid) for sid in seed_ids]
    all_edges: list[tuple] = []

    for _ in range(4):  # 4 hops max
        if not frontier or len(visited_type_ids) >= limit:
            break
        new_frontier: list[tuple[str, str]] = []
        for entity_type, entity_id in frontier:
            if (entity_type, entity_id) in visited_type_ids:
                continue
            visited_type_ids.add((entity_type, entity_id))

            rows = db.execute("""
                SELECT source_type, source_id, target_type, target_id, relationship
                FROM graph_edges
                WHERE (source_type = ? AND source_id = ?)
                   OR (target_type = ? AND target_id = ?)
            """, [entity_type, entity_id, entity_type, entity_id]).fetchall()

            for row in rows:
                all_edges.append(row)
                src_key = (row[0], str(row[1]))
                tgt_key = (row[2], str(row[3]))
                if src_key not in visited_type_ids:
                    new_frontier.append(src_key)
                if tgt_key not in visited_type_ids:
                    new_frontier.append(tgt_key)
        frontier = new_frontier

    # Deduplicate edges
    seen_edges: set[tuple] = set()
    unique_edges: list[tuple] = []
    for e in all_edges:
        key = (e[0], str(e[1]), e[2], str(e[3]), e[4])
        if key not in seen_edges:
            seen_edges.add(key)
            unique_edges.append(e)

    # Collect nodes referenced by edges
    node_keys = set()
    for e in unique_edges:
        node_keys.add((e[0], str(e[1])))
        node_keys.add((e[2], str(e[3])))

    # Also add seed nodes even if no edges
    for k in visited_type_ids:
        node_keys.add(k)

    node_keys = list(node_keys)[:limit]

    # Fetch node details
    nodes: list[GraphNode] = []
    for entity_type, entity_id in node_keys:
        row = db.execute(
            "SELECT entity_type, entity_id, label, properties FROM graph_nodes WHERE entity_type = ? AND entity_id = ?",
            [entity_type, entity_id],
        ).fetchone()
        if row:
            nodes.append(_row_to_node(row))
        else:
            # Node exists in edges but not in graph_nodes — create a minimal placeholder
            nodes.append(GraphNode(
                id=_make_node_id(entity_type, entity_id),
                entity_type=entity_type,
                entity_id=entity_id,
                label=f"{entity_type}:{entity_id}",
                properties={},
            ))

    # Only return edges where BOTH endpoints are in the returned node set
    final_node_keys = {(n.entity_type, n.entity_id) for n in nodes}
    return GraphResponse(nodes=nodes, edges=[
        _row_to_edge(e) for e in unique_edges
        if (e[0], str(e[1])) in final_node_keys and (e[2], str(e[3])) in final_node_keys
    ])


def get_node(db, entity_type: str, entity_id: str) -> GraphNode | None:
    row = db.execute(
        "SELECT entity_type, entity_id, label, properties FROM graph_nodes WHERE entity_type = ? AND entity_id = ?",
        [entity_type, entity_id],
    ).fetchone()
    return _row_to_node(row) if row else None


def get_neighbors(db, entity_type: str, entity_id: str) -> GraphResponse:
    """Return all 1-hop neighbors and the edges connecting them."""
    edge_rows = db.execute("""
        SELECT source_type, source_id, target_type, target_id, relationship
        FROM graph_edges
        WHERE (source_type = ? AND source_id = ?)
           OR (target_type = ? AND target_id = ?)
    """, [entity_type, entity_id, entity_type, entity_id]).fetchall()

    node_keys: set[tuple[str, str]] = {(entity_type, entity_id)}
    for row in edge_rows:
        node_keys.add((row[0], str(row[1])))
        node_keys.add((row[2], str(row[3])))

    nodes: list[GraphNode] = []
    for et, eid in node_keys:
        row = db.execute(
            "SELECT entity_type, entity_id, label, properties FROM graph_nodes WHERE entity_type = ? AND entity_id = ?",
            [et, eid],
        ).fetchone()
        if row:
            nodes.append(_row_to_node(row))
        else:
            nodes.append(GraphNode(
                id=_make_node_id(et, eid),
                entity_type=et,
                entity_id=eid,
                label=f"{et}:{eid}",
                properties={},
            ))

    return GraphResponse(nodes=nodes, edges=[_row_to_edge(r) for r in edge_rows])


def trace_flow(db, entity_type: str, entity_id: str, max_depth: int = 8) -> GraphResponse:
    """
    BFS/DFS traversal starting from this node — returns the full connected sub-graph.
    Uses the graph_edges adjacency table exclusively.
    """
    visited_keys: set[tuple[str, str]] = set()
    frontier = [(entity_type, entity_id)]
    all_edge_rows: list[tuple] = []

    depth = 0
    while frontier and depth < max_depth:
        next_frontier: list[tuple[str, str]] = []
        for et, eid in frontier:
            if (et, eid) in visited_keys:
                continue
            visited_keys.add((et, eid))

            rows = db.execute("""
                SELECT source_type, source_id, target_type, target_id, relationship
                FROM graph_edges
                WHERE (source_type = ? AND source_id = ?)
                   OR (target_type = ? AND target_id = ?)
            """, [et, eid, et, eid]).fetchall()

            for row in rows:
                all_edge_rows.append(row)
                src_key = (row[0], str(row[1]))
                tgt_key = (row[2], str(row[3]))
                if src_key not in visited_keys:
                    next_frontier.append(src_key)
                if tgt_key not in visited_keys:
                    next_frontier.append(tgt_key)

        frontier = next_frontier
        depth += 1

    # Deduplicate edges
    seen: set[tuple] = set()
    unique_edges: list[tuple] = []
    for e in all_edge_rows:
        key = (e[0], str(e[1]), e[2], str(e[3]), e[4])
        if key not in seen:
            seen.add(key)
            unique_edges.append(e)

    # Collect all node keys
    all_keys = set(visited_keys)
    for e in unique_edges:
        all_keys.add((e[0], str(e[1])))
        all_keys.add((e[2], str(e[3])))

    nodes: list[GraphNode] = []
    for et, eid in all_keys:
        row = db.execute(
            "SELECT entity_type, entity_id, label, properties FROM graph_nodes WHERE entity_type = ? AND entity_id = ?",
            [et, eid],
        ).fetchone()
        if row:
            nodes.append(_row_to_node(row))
        else:
            nodes.append(GraphNode(
                id=_make_node_id(et, eid),
                entity_type=et,
                entity_id=eid,
                label=f"{et}:{eid}",
                properties={},
            ))

    return GraphResponse(nodes=nodes, edges=[_row_to_edge(e) for e in unique_edges])


def get_stats(db) -> GraphStats:
    total_nodes = db.execute("SELECT COUNT(*) FROM graph_nodes").fetchone()[0]
    total_edges = db.execute("SELECT COUNT(*) FROM graph_edges").fetchone()[0]

    type_rows = db.execute(
        "SELECT entity_type, COUNT(*) FROM graph_nodes GROUP BY entity_type ORDER BY COUNT(*) DESC"
    ).fetchall()
    by_entity_type = {r[0]: r[1] for r in type_rows}

    rel_rows = db.execute(
        "SELECT relationship, COUNT(*) FROM graph_edges GROUP BY relationship ORDER BY COUNT(*) DESC"
    ).fetchall()
    by_relationship = {r[0]: r[1] for r in rel_rows}

    return GraphStats(
        total_nodes=total_nodes,
        total_edges=total_edges,
        by_entity_type=by_entity_type,
        by_relationship=by_relationship,
    )


def filter_graph(db, entity_types: list[str] | None = None, limit: int = 100) -> GraphResponse:
    """Return nodes filtered by entity type with their connecting edges."""
    if entity_types:
        placeholders = ", ".join(["?" for _ in entity_types])
        node_rows = db.execute(
            f"SELECT entity_type, entity_id, label, properties FROM graph_nodes WHERE entity_type IN ({placeholders}) LIMIT ?",
            entity_types + [limit],
        ).fetchall()
    else:
        node_rows = db.execute(
            "SELECT entity_type, entity_id, label, properties FROM graph_nodes LIMIT ?",
            [limit],
        ).fetchall()

    nodes = [_row_to_node(r) for r in node_rows]
    node_keys = {(n.entity_type, n.entity_id) for n in nodes}

    # Return only edges where BOTH endpoints are in our node set
    all_edge_rows = db.execute(
        "SELECT source_type, source_id, target_type, target_id, relationship FROM graph_edges LIMIT 5000"
    ).fetchall()

    edges = [
        _row_to_edge(r)
        for r in all_edge_rows
        if (r[0], str(r[1])) in node_keys and (r[2], str(r[3])) in node_keys
    ]

    return GraphResponse(nodes=nodes, edges=edges)
