"""
SQL executor — validates and safely runs SELECT queries against DuckDB.
"""

import re
import logging
from typing import Any

import pandas as pd

logger = logging.getLogger(__name__)

# DDL/DML keywords that must never appear in user-generated SQL
_FORBIDDEN_PATTERNS = [
    r"\bDROP\b",
    r"\bDELETE\b",
    r"\bUPDATE\b",
    r"\bINSERT\b",
    r"\bALTER\b",
    r"\bCREATE\b",
    r"\bTRUNCATE\b",
    r"\bGRANT\b",
    r"\bREVOKE\b",
    r"\bEXEC\b",
    r"\bEXECUTE\b",
    r"\bCALL\b",
    r"\bCOPY\b",
    r"\bATTACH\b",
    r"\bDETACH\b",
    r"\bIMPORT\b",
    r"\bEXPORT\b",
    r"\bINSTALL\b",
    r"\bLOAD\b",
]


def validate_sql(sql: str) -> tuple[bool, str]:
    """
    Returns (is_valid, reason).
    Only SELECT / WITH…SELECT queries are permitted.
    """
    if not sql or not sql.strip():
        return False, "Empty SQL"

    upper = sql.upper().strip()

    # Must start with SELECT or WITH (for CTEs)
    if not (upper.startswith("SELECT") or upper.startswith("WITH")):
        return False, "Query must be a SELECT statement"

    for pattern in _FORBIDDEN_PATTERNS:
        if re.search(pattern, upper):
            return False, f"Forbidden keyword detected: {pattern}"

    return True, "OK"


def execute_query(db, sql: str, row_limit: int = 50) -> tuple[pd.DataFrame | None, str | None]:
    """
    Execute *sql* and return (dataframe, error_message).
    On success, error_message is None.
    On failure, dataframe is None and error_message contains the reason.
    """
    is_valid, reason = validate_sql(sql)
    if not is_valid:
        logger.warning("SQL validation failed: %s\nSQL: %s", reason, sql)
        return None, f"SQL validation failed: {reason}"

    try:
        df = db.execute(sql).fetchdf()
        if len(df) > row_limit:
            df = df.head(row_limit)
        return df, None
    except Exception as exc:
        logger.error("Query execution failed: %s\nSQL: %s", exc, sql)
        return None, str(exc)


def extract_entity_ids(df: pd.DataFrame) -> list[dict[str, str]]:
    """
    Scan dataframe columns for entity IDs to highlight in the graph.
    Returns a list of {"type": "...", "id": "..."} dicts.
    """
    ENTITY_COLUMNS = {
        "salesorder": "SalesOrder",
        "sales_order": "SalesOrder",
        "delivery": "Delivery",
        "billingdocument": "BillingDocument",
        "billing_document": "BillingDocument",
        "journalentry": "JournalEntry",
        "journal_entry": "JournalEntry",
        "accountingdocument": "JournalEntry",
        "customer": "Customer",
        "soldtoparty": "Customer",
        "shiptoparty": "Customer",
        "material": "Material",
        "plant": "Plant",
    }

    entities: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()

    for col in df.columns:
        col_lower = col.lower()
        entity_type = ENTITY_COLUMNS.get(col_lower)
        if entity_type:
            for val in df[col].dropna().unique():
                val_str = str(val)
                key = (entity_type, val_str)
                if key not in seen:
                    seen.add(key)
                    entities.append({"type": entity_type, "id": val_str})

    return entities[:20]  # Cap at 20 highlighted entities
