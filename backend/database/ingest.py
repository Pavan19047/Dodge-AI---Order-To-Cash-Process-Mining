"""
JSONL → DuckDB ingestion.

Strategy:
1. Discover every subdirectory under data/sap-o2c-data/ (or data/ itself).
2. For each subdirectory that contains *.jsonl files, read them all into a
   DuckDB table named after the directory (using read_json_auto with a glob).
3. Fall back to CSV reading if any *.csv files exist at the top level.
4. Expose the loaded table list and their columns for downstream use.

Run this module directly to trigger ingestion:
    python -m database.ingest
"""

import logging
from pathlib import Path

from config import DATA_DIR
from database.connection import Database
from database.schema import create_graph_tables

logger = logging.getLogger(__name__)

# Sub-directory name inside DATA_DIR where the SAP O2C JSONL files live.
SAP_DATA_SUBDIR = "sap-o2c-data"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _normalize_table_name(name: str) -> str:
    return name.lower().replace(" ", "_").replace("-", "_")


def _get_columns(db, table: str) -> list[str]:
    rows = db.execute(f"DESCRIBE {table}").fetchall()
    return [r[0] for r in rows]


# ---------------------------------------------------------------------------
# Main ingestion
# ---------------------------------------------------------------------------

def ingest_all(data_dir: Path | None = None) -> dict[str, list[str]]:
    """
    Load all JSONL / CSV data under *data_dir* into DuckDB tables.
    Returns a mapping of {table_name: [column, ...]} for every loaded table.
    """
    if data_dir is None:
        data_dir = DATA_DIR

    db = Database.get()
    create_graph_tables(db)

    table_columns: dict[str, list[str]] = {}

    # 1. Prefer the SAP JSONL directory structure
    jsonl_root = data_dir / SAP_DATA_SUBDIR
    if jsonl_root.is_dir():
        for entity_dir in sorted(jsonl_root.iterdir()):
            if not entity_dir.is_dir():
                continue
            jsonl_files = sorted(entity_dir.glob("*.jsonl"))
            if not jsonl_files:
                continue
            table_name = _normalize_table_name(entity_dir.name)
            # DuckDB glob pattern for all JSONL files in this dir
            glob_path = str(entity_dir / "*.jsonl").replace("\\", "/")
            try:
                db.execute(f"""
                    CREATE OR REPLACE TABLE {table_name} AS
                    SELECT * FROM read_json_auto('{glob_path}', ignore_errors=true)
                """)
                cols = _get_columns(db, table_name)
                table_columns[table_name] = cols
                row_count = db.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0]
                logger.info("Loaded %-50s → %-50s (%d rows)", entity_dir.name, table_name, row_count)
            except Exception as exc:
                logger.error("Failed to load JSONL from %s: %s", entity_dir.name, exc)

    # 2. Fall back: top-level CSV files (legacy support)
    csv_files = sorted(data_dir.glob("*.csv"))
    for csv_file in csv_files:
        table_name = _normalize_table_name(csv_file.stem)
        try:
            db.execute(f"""
                CREATE OR REPLACE TABLE {table_name} AS
                SELECT * FROM read_csv_auto('{csv_file}', header=true, ignore_errors=true)
            """)
            cols = _get_columns(db, table_name)
            table_columns[table_name] = cols
            row_count = db.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0]
            logger.info("Loaded CSV %-40s → %s  (%d rows)", csv_file.name, table_name, row_count)
        except Exception as exc:
            logger.error("Failed to load CSV %s: %s", csv_file.name, exc)

    if not table_columns:
        logger.warning("No data files found under %s", data_dir)
        return table_columns

    db.commit()
    logger.info("Ingestion complete. Tables: %s", list(table_columns.keys()))
    return table_columns


# ---------------------------------------------------------------------------
# Schema helpers
# ---------------------------------------------------------------------------

_schema_cache: str | None = None


def get_schema_context_slim(db=None) -> str:
    """
    Compact schema for LLM prompts — column names and row counts only.
    Result is cached after the first call so large prompts aren't rebuilt
    on every chat request.
    """
    global _schema_cache
    if _schema_cache is not None:
        return _schema_cache

    if db is None:
        db = Database.get()

    EXCLUDE = {"graph_nodes", "graph_edges"}
    lines: list[str] = []

    tables = [r[0] for r in db.execute("SHOW TABLES").fetchall()]
    for table in sorted(tables):
        if table in EXCLUDE:
            continue
        try:
            cols = _get_columns(db, table)
            count = db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            lines.append(f"{table} ({count} rows): {', '.join(cols)}")
        except Exception:
            continue

    lines.append(
        "graph_edges (adjacency): source_type, source_id, target_type, target_id, relationship"
    )
    lines.append(
        "  relationships: SalesOrder→Delivery, Delivery→BillingDocument, "
        "BillingDocument→JournalEntry, SalesOrder→Customer, SalesOrder→Material, "
        "SalesOrder→Plant"
    )

    _schema_cache = "\n".join(lines)
    return _schema_cache


def get_schema_context(db=None) -> str:
    """
    Return a human-readable schema string suitable for injection into LLM prompts.
    Lists every non-graph table with its columns and a row count.
    """
    if db is None:
        db = Database.get()

    EXCLUDE = {"graph_nodes", "graph_edges"}
    lines: list[str] = []

    tables = [r[0] for r in db.execute("SHOW TABLES").fetchall()]
    for table in sorted(tables):
        if table in EXCLUDE:
            continue
        try:
            cols = _get_columns(db, table)
            count = db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            lines.append(f"TABLE {table} ({count} rows)")
            lines.append(f"  COLUMNS: {', '.join(cols)}")
            # Show 2 sample values per column to help the LLM understand data formats
            try:
                sample = db.execute(
                    f"SELECT * FROM {table} LIMIT 2"
                ).fetchdf()
                for _, row in sample.iterrows():
                    row_str = ", ".join(
                        f"{k}={repr(v)}" for k, v in row.items()
                    )
                    lines.append(f"  SAMPLE: {row_str}")
            except Exception:
                pass
            lines.append("")
        except Exception:
            continue

    # Always include graph structure description
    lines.append("TABLE graph_edges  (adjacency table for the Order-to-Cash graph)")
    lines.append("  COLUMNS: source_type, source_id, target_type, target_id, relationship, metadata")
    lines.append("  RELATIONSHIPS: SalesOrder→Delivery, Delivery→BillingDocument, BillingDocument→JournalEntry,")
    lines.append("                 SalesOrder→Customer, Delivery→Customer, SalesOrder→Material, etc.")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")
    table_cols = ingest_all()
    print("\nLoaded tables:")
    for t, cols in table_cols.items():
        print(f"  {t:40s} {cols}")
