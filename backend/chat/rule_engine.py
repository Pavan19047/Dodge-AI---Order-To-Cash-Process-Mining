"""
Rule-based fallback for intent classification and SQL generation.

Used when the Gemini API is unavailable (quota exhausted, key missing, etc.).
Covers the most common O2C query patterns via keyword matching + templated SQL.
"""

from __future__ import annotations

import re
import logging
from typing import Literal

import pandas as pd

logger = logging.getLogger(__name__)

IntentType = Literal[
    "TRACE_FLOW",
    "AGGREGATION",
    "ANOMALY_DETECTION",
    "ENTITY_LOOKUP",
    "RELATIONSHIP_QUERY",
    "OFF_TOPIC",
]

# ---------------------------------------------------------------------------
# Keyword → intent mapping  (checked in order; first match wins)
# ---------------------------------------------------------------------------

_INTENT_RULES: list[tuple[str, IntentType]] = [
    # OFF_TOPIC
    (r"\b(weather|joke|recipe|news|sport|football|movie|music|song|stock price)\b", "OFF_TOPIC"),
    # TRACE_FLOW — "trace / lifecycle / journey / flow" for a specific doc
    (r"\b(trace|lifecycle|life.?cycle|journey|end.to.end|full flow|order flow)\b", "TRACE_FLOW"),
    (r"\bso[-\s]?\d{5,}\b", "TRACE_FLOW"),          # e.g. "SO-10001" or "SO10001"
    (r"\border\s+\d{5,}", "TRACE_FLOW"),
    # ANOMALY_DETECTION — incomplete / blocked / stuck / missing
    (r"\b(anomal[yi]?|anomalies|anomaly|blocked|stuck|incomplete|missing|undelivered|unbilled|pending|overdue|not delivered|never billed|no delivery|no billing|no invoice|no payment)\b", "ANOMALY_DETECTION"),
    # ENTITY_LOOKUP — "show me / details of / info on" + specific ID-like token
    (r"\b(details?|info|information|profile|show me|look up|find)\b.{0,40}\b(customer|product|material|plant|sales area|billing)\b", "ENTITY_LOOKUP"),
    (r"\bcustomer\s+(id|number|#)\s*[:\-]?\s*\d+", "ENTITY_LOOKUP"),
    # RELATIONSHIP_QUERY — "which / what … connected / linked / related / associated"
    (r"\b(which|what).{0,30}\b(connect|link|relat|associat)\b", "RELATIONSHIP_QUERY"),
    (r"\b(connect|link|relat|associat).{0,30}\b(which|what)\b", "RELATIONSHIP_QUERY"),
    (r"\brelated to\b", "RELATIONSHIP_QUERY"),
    # AGGREGATION — count, total, sum, average, top, most, least, how many, ranking
    (r"\b(count|total|sum|average|avg|top\s+\d|most|least|how many|rank|volume|revenue|breakdown|distribut|percent|ratio|highest|lowest|best|worst|largest|smallest)\b", "AGGREGATION"),
]


def classify_intent(query: str) -> IntentType:
    q = query.lower()
    for pattern, intent in _INTENT_RULES:
        if re.search(pattern, q):
            return intent
    # Default: try an aggregation since most O2C questions are summary-oriented
    return "AGGREGATION"


# ---------------------------------------------------------------------------
# Template SQL library
# ---------------------------------------------------------------------------

def _extract_id(query: str) -> str | None:
    """Pull the first numeric ID-like token from the query."""
    m = re.search(r"\b(\d{5,})\b", query)
    return m.group(1) if m else None


_AGGREGATION_TEMPLATES: list[tuple[str, str]] = [
    # Top customers (must come before generic revenue/billing pattern)
    (r"\b(top|best|biggest|largest).{0,20}customer",
     """SELECT
        soh.soldToParty AS customer_id,
        bp.businessPartnerName AS customer_name,
        COUNT(DISTINCT soh.salesOrder) AS order_count,
        ROUND(SUM(TRY_CAST(soh.totalNetAmount AS DOUBLE)), 2) AS total_net_value
     FROM sales_order_headers soh
     LEFT JOIN business_partners bp ON bp.customer = soh.soldToParty
     GROUP BY soh.soldToParty, bp.businessPartnerName
     ORDER BY total_net_value DESC NULLS LAST
     LIMIT 20"""),
    # Product / material sales (must come before generic revenue pattern)
    (r"\b(top|best|popular|most).{0,20}(product|material)\b",
     """SELECT
        soi.material,
        pd.productDescription AS material_description,
        COUNT(*) AS line_count,
        ROUND(SUM(TRY_CAST(soi.requestedQuantity AS DOUBLE)), 2) AS total_qty,
        ROUND(SUM(TRY_CAST(soi.netAmount AS DOUBLE)), 2) AS total_net_value
     FROM sales_order_items soi
     LEFT JOIN product_descriptions pd ON soi.material = pd.product
     GROUP BY soi.material, pd.productDescription
     ORDER BY total_net_value DESC NULLS LAST
     LIMIT 20"""),
    # Revenue / billing by month
    (r"\b(revenue|billing|billed|invoice)\b",
     """SELECT
        CAST(billingDocumentDate AS VARCHAR)[:7] AS month,
        COUNT(*) AS invoice_count,
        ROUND(SUM(TRY_CAST(totalNetAmount AS DOUBLE)), 2) AS total_net_value,
        transactionCurrency AS currency
     FROM billing_document_headers
     WHERE billingDocumentDate IS NOT NULL
     GROUP BY month, transactionCurrency
     ORDER BY month DESC
     LIMIT 50"""),
    # Payments / receivable
    (r"\b(payment|paid|receivable|collected)\b",
     """SELECT
        financialAccountType,
        COUNT(*) AS payment_count,
        ROUND(SUM(TRY_CAST(amountInTransactionCurrency AS DOUBLE)), 2) AS total_amount,
        transactionCurrency AS currency
     FROM payments_accounts_receivable
     GROUP BY financialAccountType, transactionCurrency
     ORDER BY total_amount DESC NULLS LAST
     LIMIT 50"""),
    # Delivery status / fulfilment
    (r"\b(deliver|shipment|fulfilment|fulfillment)\b",
     """SELECT
        overallGoodsMovementStatus AS delivery_status,
        COUNT(*) AS delivery_count
     FROM outbound_delivery_headers
     GROUP BY overallGoodsMovementStatus
     ORDER BY delivery_count DESC
     LIMIT 50"""),
    # Order count by customer
    (r"\border.{0,20}(customer|per customer|by customer)\b",
     """SELECT
        soh.soldToParty AS customer_id,
        bp.businessPartnerName AS customer_name,
        COUNT(DISTINCT soh.salesOrder) AS order_count
     FROM sales_order_headers soh
     LEFT JOIN business_partners bp ON bp.customer = soh.soldToParty
     GROUP BY soh.soldToParty, bp.businessPartnerName
     ORDER BY order_count DESC
     LIMIT 50"""),
    # Sales by shipping point / plant
    (r"\b(plant|location|warehouse|distribution|shipping)\b",
     """SELECT
        shippingPoint AS shipping_point,
        COUNT(*) AS delivery_count
     FROM outbound_delivery_headers
     GROUP BY shippingPoint
     ORDER BY delivery_count DESC
     LIMIT 50"""),
    # Status breakdown of orders
    (r"\b(status|order status|breakdown)\b",
     """SELECT
        overallDeliveryStatus AS order_status,
        COUNT(*) AS order_count,
        ROUND(SUM(TRY_CAST(totalNetAmount AS DOUBLE)), 2) AS total_net_value
     FROM sales_order_headers
     GROUP BY overallDeliveryStatus
     ORDER BY order_count DESC
     LIMIT 50"""),
]

# Generic aggregation fallback
_AGGREGATION_FALLBACK = """SELECT
    overallDeliveryStatus AS order_status,
    COUNT(*) AS order_count,
    ROUND(SUM(TRY_CAST(totalNetAmount AS DOUBLE)), 2) AS total_net_value
FROM sales_order_headers
GROUP BY overallDeliveryStatus
ORDER BY order_count DESC
LIMIT 50"""

_ANOMALY_TEMPLATES: list[tuple[str, str]] = [
    (r"\b(undelivered|not delivered|no delivery)\b",
     """SELECT
        soh.salesOrder AS sales_order,
        soh.soldToParty AS customer,
        soh.creationDate AS order_date,
        soh.overallDeliveryStatus AS status
     FROM sales_order_headers soh
     WHERE NOT EXISTS (
        SELECT 1 FROM outbound_delivery_items odi
        WHERE odi.referenceSdDocument = soh.salesOrder
     )
     ORDER BY soh.creationDate DESC
     LIMIT 50"""),
    (r"\b(unbilled|not billed|no billing|no invoice)\b",
     """SELECT
        odh.deliveryDocument AS delivery_id,
        odh.shippingPoint AS shipping_point,
        odh.actualGoodsMovementDate AS goods_movement_date,
        odh.overallGoodsMovementStatus AS status
     FROM outbound_delivery_headers odh
     WHERE NOT EXISTS (
        SELECT 1 FROM billing_document_items bdi
        WHERE bdi.referenceSdDocument = odh.deliveryDocument
     )
     AND odh.actualGoodsMovementDate IS NOT NULL
     ORDER BY odh.actualGoodsMovementDate DESC
     LIMIT 50"""),
    (r"\b(unpaid|no payment|outstanding|overdue)\b",
     """SELECT
        h.billingDocument AS billing_document,
        h.soldToParty AS customer,
        CAST(h.billingDocumentDate AS VARCHAR)[:10] AS billing_date,
        h.totalNetAmount AS net_value,
        h.transactionCurrency AS currency
     FROM billing_document_headers h
     WHERE NOT EXISTS (
        SELECT 1 FROM payments_accounts_receivable p
        WHERE p.accountingDocument = h.accountingDocument
     )
     ORDER BY h.billingDocumentDate DESC
     LIMIT 50"""),
    (r"\b(incomplete|missing|broken|stuck|blocked|pending)\b",
     """SELECT
        soh.salesOrder AS sales_order,
        soh.soldToParty AS customer,
        soh.creationDate AS order_date,
        soh.overallDeliveryStatus AS status,
        CASE
          WHEN NOT EXISTS (
            SELECT 1 FROM outbound_delivery_items odi
            WHERE odi.referenceSdDocument = soh.salesOrder
          ) THEN 'Missing Delivery'
          WHEN NOT EXISTS (
            SELECT 1 FROM billing_document_items bdi
            JOIN outbound_delivery_items odi ON odi.deliveryDocument = bdi.referenceSdDocument
            WHERE odi.referenceSdDocument = soh.salesOrder
          ) THEN 'Delivered but Not Billed'
          ELSE 'Billed but Not Paid'
        END AS gap
     FROM sales_order_headers soh
     WHERE NOT EXISTS (
        SELECT 1 FROM payments_accounts_receivable par
        JOIN billing_document_headers bdh ON bdh.accountingDocument = par.accountingDocument
        JOIN billing_document_items bdi ON bdi.billingDocument = bdh.billingDocument
        JOIN outbound_delivery_items odi ON odi.deliveryDocument = bdi.referenceSdDocument
        WHERE odi.referenceSdDocument = soh.salesOrder
     )
     ORDER BY soh.creationDate DESC
     LIMIT 50"""),
]

_ANOMALY_FALLBACK = """SELECT
    soh.salesOrder AS sales_order,
    soh.soldToParty AS customer,
    soh.creationDate AS order_date,
    soh.overallDeliveryStatus AS status,
    CASE
      WHEN NOT EXISTS (
        SELECT 1 FROM outbound_delivery_items odi
        WHERE odi.referenceSdDocument = soh.salesOrder
      ) THEN 'Missing Delivery'
      WHEN NOT EXISTS (
        SELECT 1 FROM billing_document_items bdi
        JOIN outbound_delivery_items odi ON odi.deliveryDocument = bdi.referenceSdDocument
        WHERE odi.referenceSdDocument = soh.salesOrder
      ) THEN 'Delivered but Not Billed'
      ELSE 'Incomplete Flow'
    END AS anomaly_type
FROM sales_order_headers soh
WHERE NOT EXISTS (
    SELECT 1 FROM payments_accounts_receivable par
    JOIN billing_document_headers bdh ON bdh.accountingDocument = par.accountingDocument
    JOIN billing_document_items bdi ON bdi.billingDocument = bdh.billingDocument
    JOIN outbound_delivery_items odi ON odi.deliveryDocument = bdi.referenceSdDocument
    WHERE odi.referenceSdDocument = soh.salesOrder
)
ORDER BY soh.creationDate DESC
LIMIT 50"""


def _trace_flow_sql(entity_id: str | None) -> str:
    if entity_id:
        return f"""WITH RECURSIVE flow(source_type, source_id, target_type, target_id, relationship, depth) AS (
    SELECT source_type, source_id, target_type, target_id, relationship, 1
    FROM graph_edges
    WHERE (source_id = '{entity_id}' OR target_id = '{entity_id}')
    UNION ALL
    SELECT e.source_type, e.source_id, e.target_type, e.target_id, e.relationship, f.depth + 1
    FROM graph_edges e
    JOIN flow f ON (e.source_id = f.target_id OR e.source_id = f.source_id)
    WHERE f.depth < 6
)
SELECT DISTINCT source_type, source_id, relationship, target_type, target_id
FROM flow
ORDER BY source_type, source_id
LIMIT 50"""
    return """SELECT source_type, source_id, relationship, target_type, target_id
FROM graph_edges
LIMIT 50"""


def _entity_lookup_sql(query: str) -> str:
    q = query.lower()
    entity_id = _extract_id(query)
    id_filter = f"= '{entity_id}'" if entity_id else "IS NOT NULL"

    if re.search(r"\bcustomer\b", q):
        return f"""SELECT businessPartner, customer, businessPartnerFullName, businessPartnerName,
    firstName, lastName, organizationBpName1
FROM business_partners
WHERE customer {id_filter}
LIMIT 20"""
    if re.search(r"\b(product|material)\b", q):
        return f"""SELECT p.product, p.productType, pd.productDescription
FROM products p
LEFT JOIN product_descriptions pd ON p.product = pd.product
WHERE p.product {id_filter}
LIMIT 20"""
    if re.search(r"\b(order|so)\b", q):
        return f"""SELECT h.salesOrder, h.soldToParty, h.creationDate, h.totalNetAmount,
    h.transactionCurrency, h.overallDeliveryStatus,
    COUNT(i.salesOrderItem) AS line_items
FROM sales_order_headers h
LEFT JOIN sales_order_items i ON h.salesOrder = i.salesOrder
WHERE h.salesOrder {id_filter}
GROUP BY ALL
LIMIT 20"""
    if re.search(r"\b(delivery|deliveries)\b", q):
        return f"""SELECT deliveryDocument, shippingPoint, actualGoodsMovementDate,
    overallGoodsMovementStatus, overallPickingStatus
FROM outbound_delivery_headers
WHERE deliveryDocument {id_filter}
LIMIT 20"""
    if re.search(r"\b(billing|invoice)\b", q):
        return f"""SELECT billingDocument, soldToParty, billingDocumentDate,
    totalNetAmount, transactionCurrency, accountingDocument
FROM billing_document_headers
WHERE billingDocument {id_filter}
LIMIT 20"""
    return f"""SELECT salesOrder, soldToParty, creationDate, totalNetAmount,
    transactionCurrency, overallDeliveryStatus
FROM sales_order_headers
WHERE salesOrder {id_filter}
LIMIT 20"""


def _relationship_sql(query: str) -> str:
    q = query.lower()
    entity_id = _extract_id(query)

    if entity_id:
        return f"""SELECT source_type, source_id, relationship, target_type, target_id
FROM graph_edges
WHERE source_id = '{entity_id}' OR target_id = '{entity_id}'
LIMIT 50"""
    if re.search(r"\bcustomer\b", q):
        return """SELECT bp.customer AS customer_id, bp.businessPartnerName AS customer_name,
    COUNT(DISTINCT soh.salesOrder) AS orders,
    COUNT(DISTINCT bdh.billingDocument) AS invoices
FROM business_partners bp
LEFT JOIN sales_order_headers soh ON soh.soldToParty = bp.customer
LEFT JOIN billing_document_headers bdh ON bdh.soldToParty = bp.customer
GROUP BY bp.customer, bp.businessPartnerName
ORDER BY orders DESC
LIMIT 50"""
    return """SELECT source_type, source_id, relationship, target_type, target_id
FROM graph_edges
LIMIT 50"""


def _pick_aggregation_sql(query: str) -> str:
    q = query.lower()
    for pattern, sql in _AGGREGATION_TEMPLATES:
        if re.search(pattern, q):
            return sql
    return _AGGREGATION_FALLBACK


def _pick_anomaly_sql(query: str) -> str:
    q = query.lower()
    for pattern, sql in _ANOMALY_TEMPLATES:
        if re.search(pattern, q):
            return sql
    return _ANOMALY_FALLBACK


def generate_sql(intent: IntentType, query: str) -> str | None:
    """Return a pre-built SQL string for the given intent, or None for OFF_TOPIC."""
    if intent == "OFF_TOPIC":
        return None
    if intent == "TRACE_FLOW":
        return _trace_flow_sql(_extract_id(query))
    if intent == "ANOMALY_DETECTION":
        return _pick_anomaly_sql(query)
    if intent == "ENTITY_LOOKUP":
        return _entity_lookup_sql(query)
    if intent == "RELATIONSHIP_QUERY":
        return _relationship_sql(query)
    # AGGREGATION (default)
    return _pick_aggregation_sql(query)


# ---------------------------------------------------------------------------
# Natural-language summary (no LLM)
# ---------------------------------------------------------------------------

def _format_value(v) -> str:
    if v is None:
        return "N/A"
    try:
        f = float(v)
        return f"{f:,.2f}" if f != int(f) else f"{int(f):,}"
    except (TypeError, ValueError):
        return str(v)


def build_summary(intent: IntentType, query: str, df: pd.DataFrame) -> str:
    """Generate a terse natural-language summary from the result DataFrame."""
    rows = len(df)
    if rows == 0:
        return "No matching records found for your query."

    cols = list(df.columns)

    if intent == "TRACE_FLOW":
        entity_id = _extract_id(query) or "the entity"
        return (
            f"Found {rows} step(s) in the lifecycle of **{entity_id}**. "
            "The table below shows the full Order-to-Cash flow."
        )

    if intent == "ANOMALY_DETECTION":
        return (
            f"Detected **{rows} order(s)** with incomplete or broken O2C flows. "
            "See the 'anomaly_type' or 'gap' column for the specific issue."
        )

    if intent == "ENTITY_LOOKUP":
        return f"Found **{rows} record(s)**. Details are shown in the table below."

    if intent == "RELATIONSHIP_QUERY":
        return (
            f"Found **{rows} relationship(s)**. "
            "The table shows how entities are connected in the O2C graph."
        )

    # AGGREGATION — try to craft a meaningful sentence
    # Look for numeric columns and the first categorical column
    num_cols = [c for c in cols if df[c].dtype in ("float64", "int64") or
                _is_numeric_col(df, c)]
    cat_cols = [c for c in cols if c not in num_cols]

    if num_cols and cat_cols:
        top_row = df.iloc[0]
        cat_val = top_row[cat_cols[0]]
        num_val = _format_value(top_row[num_cols[0]])
        return (
            f"Returned **{rows} group(s)**. "
            f"Top result: **{cat_val}** with **{num_cols[0]}** = {num_val}. "
            "Full breakdown is in the table below."
        )

    if num_cols:
        total = df[num_cols[0]].apply(lambda x: _safe_float(x)).sum()
        return (
            f"Aggregation returned **{rows} row(s)**. "
            f"Total {num_cols[0]}: **{total:,.2f}**."
        )

    return f"Query returned **{rows} row(s)**. See the table below."


def _is_numeric_col(df: pd.DataFrame, col: str) -> bool:
    try:
        pd.to_numeric(df[col], errors="raise")
        return True
    except (ValueError, TypeError):
        return False


def _safe_float(v) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0
