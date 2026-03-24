"""
guardrails.py — Fast pre-filter before touching the LLM.
"""

DOMAIN_KEYWORDS = {
    "order", "delivery", "invoice", "billing", "payment", "journal",
    "customer", "material", "plant", "sales", "purchase", "document",
    "flow", "trace", "linked", "connected", "associated", "broken",
    "incomplete", "missing", "revenue", "amount", "quantity", "date",
    "shipped", "billed", "posted", "entry", "item", "product", "vendor",
    "supplier", "warehouse", "shipment", "dispatch", "goods", "stock",
    "price", "cost", "profit", "net", "gross", "total", "count", "average",
    "top", "bottom", "most", "least", "highest", "lowest", "which", "how many",
    "list", "show", "find", "get", "what", "who", "when",
}


def fast_domain_check(query: str) -> bool:
    """
    Returns True if the query plausibly relates to our O2C domain.
    This is a fast heuristic — the LLM classifier is the definitive check.
    """
    words = set(query.lower().split())
    # Also check for numeric IDs (document numbers) in the query
    has_numbers = any(w.isdigit() or (len(w) > 3 and w[:-1].isdigit()) for w in words)
    return bool(words & DOMAIN_KEYWORDS) or has_numbers
