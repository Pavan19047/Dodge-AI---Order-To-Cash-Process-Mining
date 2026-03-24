"""
DDL for all core entity tables and graph adjacency tables.
Tables are created with CREATE TABLE IF NOT EXISTS so re-running is safe.
The actual data tables are rebuilt during ingestion via CREATE OR REPLACE TABLE,
so only the graph tables need explicit DDL here.
"""

GRAPH_TABLES_DDL = [
    """
    CREATE TABLE IF NOT EXISTS graph_nodes (
        entity_type VARCHAR NOT NULL,
        entity_id   VARCHAR NOT NULL,
        label       VARCHAR,
        properties  JSON,
        PRIMARY KEY (entity_type, entity_id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS graph_edges (
        source_type  VARCHAR NOT NULL,
        source_id    VARCHAR NOT NULL,
        target_type  VARCHAR NOT NULL,
        target_id    VARCHAR NOT NULL,
        relationship VARCHAR NOT NULL,
        metadata     JSON
    )
    """,
    # Index for fast neighbor lookups
    """
    CREATE INDEX IF NOT EXISTS idx_edges_source
    ON graph_edges (source_type, source_id)
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_edges_target
    ON graph_edges (target_type, target_id)
    """,
]


def create_graph_tables(db) -> None:
    for ddl in GRAPH_TABLES_DDL:
        db.execute(ddl)
    db.commit()
