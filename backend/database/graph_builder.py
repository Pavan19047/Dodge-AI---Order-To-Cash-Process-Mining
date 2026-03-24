"""
graph_builder.py — Build graph_nodes and graph_edges from the ingested SAP O2C data.

Table → Column mapping based on the actual JSONL structure:

  sales_order_headers    salesOrder, soldToParty, totalNetAmount, overallDeliveryStatus
  sales_order_items      salesOrder, salesOrderItem, material, productionPlant, netAmount
  outbound_delivery_headers  deliveryDocument, shippingPoint
  outbound_delivery_items    deliveryDocument, referenceSdDocument, referenceSdDocumentItem, plant
  billing_document_headers   billingDocument, soldToParty, totalNetAmount, accountingDocument
  billing_document_items     billingDocument, billingDocumentItem, material, referenceSdDocument
  journal_entry_items_accounts_receivable  accountingDocument, customer, referenceDocument
  business_partners      businessPartner, customer, businessPartnerFullName, organizationBpName1
  products               product, productType
  product_descriptions   product, productDescription
  plants                 plant, plantName

Entity Relationship graph:
  SalesOrder   ──SOLD_TO──►        Customer            (sales_order_headers)
  SalesOrder   ──HAS_ITEM──►       SalesOrderItem      (sales_order_items)
  SalesOrderItem ──USES_MATERIAL──► Material           (sales_order_items)
  SalesOrderItem ──SHIPS_FROM──►   Plant               (sales_order_items.productionPlant)
  Delivery     ──FULFILLS_ORDER──► SalesOrder          (outbound_delivery_items.referenceSdDocument)
  BillingDocument ──INVOICES_DELIVERY──► Delivery      (billing_document_items.referenceSdDocument)
  BillingDocument ──BILLED_TO──►  Customer             (billing_document_headers.soldToParty)
  JournalEntry ──POSTS_FOR──►     BillingDocument      (billing_document_headers.accountingDocument)
"""

import logging

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------

def _col(columns: list[str], *candidates: str) -> str | None:
    """Return the first column name matching any candidate (case-insensitive)."""
    lower = [c.lower() for c in columns]
    for cand in candidates:
        if cand.lower() in lower:
            return columns[lower.index(cand.lower())]
    return None


def _table_exists(db, name: str) -> bool:
    tables = {r[0].lower() for r in db.execute("SHOW TABLES").fetchall()}
    return name.lower() in tables


def _cols_of(db, table: str) -> list[str]:
    return [r[0] for r in db.execute(f"DESCRIBE {table}").fetchall()]


def _insert_nodes(db, table: str, entity_type: str, id_col: str,
                  label_prefix: str, label_col: str | None = None) -> int:
    """Bulk-insert all distinct IDs from *table* into graph_nodes."""
    if not _table_exists(db, table):
        logger.warning("Table %s not found — skipping %s nodes", table, entity_type)
        return 0
    cols = _cols_of(db, table)
    if id_col not in cols:
        logger.warning("Column %s not in %s — skipping %s nodes", id_col, table, entity_type)
        return 0

    if label_col and label_col in cols:
        label_expr = (
            f"CONCAT('{label_prefix} ', CAST({id_col} AS VARCHAR),"
            f" ' – ', CAST({label_col} AS VARCHAR))"
        )
    else:
        label_expr = f"CONCAT('{label_prefix} ', CAST({id_col} AS VARCHAR))"

    json_parts = ", ".join(f"'{c}', CAST({c} AS VARCHAR)" for c in cols)
    json_expr = f"json_object({json_parts})"

    try:
        db.execute(f"""
            INSERT OR IGNORE INTO graph_nodes (entity_type, entity_id, label, properties)
            SELECT DISTINCT
                '{entity_type}',
                CAST({id_col} AS VARCHAR),
                {label_expr},
                {json_expr}
            FROM {table}
            WHERE {id_col} IS NOT NULL AND CAST({id_col} AS VARCHAR) != ''
        """)
        count = db.execute(
            f"SELECT COUNT(*) FROM graph_nodes WHERE entity_type = '{entity_type}'"
        ).fetchone()[0]
        logger.info("  Inserted %d %s nodes from %s", count, entity_type, table)
        return count
    except Exception as exc:
        logger.error("Node insert failed for %s: %s", entity_type, exc)
        return 0


def _insert_edges(db, source_type: str, source_col: str,
                  target_type: str, target_col: str,
                  relationship: str, from_table: str,
                  where: str = "") -> int:
    """Insert directional edges from a table query."""
    try:
        where_clause = f"AND {where}" if where else ""
        db.execute(f"""
            INSERT INTO graph_edges (source_type, source_id, target_type, target_id, relationship)
            SELECT DISTINCT
                '{source_type}',
                CAST({source_col} AS VARCHAR),
                '{target_type}',
                CAST({target_col} AS VARCHAR),
                '{relationship}'
            FROM {from_table}
            WHERE {source_col} IS NOT NULL AND CAST({source_col} AS VARCHAR) != ''
              AND {target_col} IS NOT NULL AND CAST({target_col} AS VARCHAR) != ''
              {where_clause}
        """)
        count = db.execute(
            f"SELECT COUNT(*) FROM graph_edges WHERE relationship = '{relationship}'"
        ).fetchone()[0]
        logger.info("  Built %d %s→%s edges (%s)", count, source_type, target_type, relationship)
        return count
    except Exception as exc:
        logger.error("Edge insert failed for %s: %s", relationship, exc)
        return 0


# ---------------------------------------------------------------------------
# Main builder
# ---------------------------------------------------------------------------

def build_graph(db) -> None:
    """
    Populate graph_nodes and graph_edges from all ingested SAP O2C tables.
    Clears existing graph data before rebuilding.
    """
    logger.info("Clearing existing graph data…")
    db.execute("DELETE FROM graph_nodes")
    db.execute("DELETE FROM graph_edges")

    all_tables = {r[0].lower() for r in db.execute("SHOW TABLES").fetchall()}

    def has(t: str) -> bool:
        return t.lower() in all_tables

    # ------------------------------------------------------------------ #
    # NODES
    # ------------------------------------------------------------------ #
    logger.info("Building nodes…")

    # SalesOrder from sales_order_headers
    if has("sales_order_headers"):
        _insert_nodes(db, "sales_order_headers", "SalesOrder",
                      "salesOrder", "SO")

    # Customer from business_partners (customer field = the customer number)
    if has("business_partners"):
        _insert_nodes(db, "business_partners", "Customer",
                      "customer", "CUST", "businessPartnerFullName")

    # Material from products, enriched with product_descriptions label
    if has("products"):
        if has("product_descriptions"):
            try:
                db.execute("""
                    INSERT OR IGNORE INTO graph_nodes (entity_type, entity_id, label, properties)
                    SELECT DISTINCT
                        'Material',
                        CAST(p.product AS VARCHAR),
                        CONCAT('MAT ', CAST(p.product AS VARCHAR),
                               ' – ', COALESCE(CAST(pd.productDescription AS VARCHAR), '')),
                        json_object('product', CAST(p.product AS VARCHAR),
                                    'productType', CAST(p.productType AS VARCHAR),
                                    'productDescription', CAST(pd.productDescription AS VARCHAR))
                    FROM products p
                    LEFT JOIN product_descriptions pd
                          ON p.product = pd.product AND pd.language = 'EN'
                    WHERE p.product IS NOT NULL
                """)
                count = db.execute(
                    "SELECT COUNT(*) FROM graph_nodes WHERE entity_type = 'Material'"
                ).fetchone()[0]
                logger.info("  Inserted %d Material nodes", count)
            except Exception as exc:
                logger.error("Material node insert failed: %s", exc)
                _insert_nodes(db, "products", "Material", "product", "MAT")
        else:
            _insert_nodes(db, "products", "Material", "product", "MAT")

    # Plant from plants
    if has("plants"):
        _insert_nodes(db, "plants", "Plant", "plant", "PLT", "plantName")

    # Delivery from outbound_delivery_headers
    if has("outbound_delivery_headers"):
        _insert_nodes(db, "outbound_delivery_headers", "Delivery",
                      "deliveryDocument", "DEL")

    # BillingDocument from billing_document_headers
    if has("billing_document_headers"):
        _insert_nodes(db, "billing_document_headers", "BillingDocument",
                      "billingDocument", "INV")

    # JournalEntry from journal_entry_items_accounts_receivable (distinct accountingDocument)
    if has("journal_entry_items_accounts_receivable"):
        _insert_nodes(db, "journal_entry_items_accounts_receivable", "JournalEntry",
                      "accountingDocument", "JE")

    # ------------------------------------------------------------------ #
    # EDGES
    # ------------------------------------------------------------------ #
    logger.info("Building edges…")

    # SalesOrder --SOLD_TO--> Customer
    if has("sales_order_headers"):
        _insert_edges(db, "SalesOrder", "salesOrder",
                      "Customer", "soldToParty",
                      "SOLD_TO", "sales_order_headers")

    # SalesOrder --HAS_ITEM--> SalesOrderItem  (composite edge via items table)
    # We skip SalesOrderItem as a node type to reduce complexity;
    # instead go: SalesOrder --USES_MATERIAL--> Material directly
    if has("sales_order_items"):
        _insert_edges(db, "SalesOrder", "salesOrder",
                      "Material", "material",
                      "ORDERED_MATERIAL", "sales_order_items")
        _insert_edges(db, "SalesOrder", "salesOrder",
                      "Plant", "productionPlant",
                      "SHIPS_FROM_PLANT", "sales_order_items",
                      "productionPlant IS NOT NULL AND productionPlant != ''")

    # Delivery --FULFILLS_ORDER--> SalesOrder
    # Link is in outbound_delivery_items: referenceSdDocument = salesOrder
    if has("outbound_delivery_items"):
        _insert_edges(db, "Delivery", "deliveryDocument",
                      "SalesOrder", "referenceSdDocument",
                      "FULFILLS_ORDER", "outbound_delivery_items")

    # BillingDocument --INVOICES_DELIVERY--> Delivery
    # Link is in billing_document_items: referenceSdDocument = deliveryDocument
    if has("billing_document_items"):
        _insert_edges(db, "BillingDocument", "billingDocument",
                      "Delivery", "referenceSdDocument",
                      "INVOICES_DELIVERY", "billing_document_items")

    # BillingDocument --BILLED_TO--> Customer
    if has("billing_document_headers"):
        _insert_edges(db, "BillingDocument", "billingDocument",
                      "Customer", "soldToParty",
                      "BILLED_TO", "billing_document_headers")

    # BillingDocument --HAS_MATERIAL--> Material
    if has("billing_document_items"):
        _insert_edges(db, "BillingDocument", "billingDocument",
                      "Material", "material",
                      "BILLED_MATERIAL", "billing_document_items")

    # JournalEntry --POSTS_FOR--> BillingDocument
    # billing_document_headers.accountingDocument = journal_entry.accountingDocument
    if has("journal_entry_items_accounts_receivable") and has("billing_document_headers"):
        try:
            db.execute("""
                INSERT INTO graph_edges (source_type, source_id, target_type, target_id, relationship)
                SELECT DISTINCT
                    'JournalEntry',
                    CAST(j.accountingDocument AS VARCHAR),
                    'BillingDocument',
                    CAST(b.billingDocument AS VARCHAR),
                    'POSTS_FOR'
                FROM journal_entry_items_accounts_receivable j
                JOIN billing_document_headers b
                  ON j.accountingDocument = b.accountingDocument
                WHERE j.accountingDocument IS NOT NULL
                  AND b.billingDocument IS NOT NULL
            """)
            count = db.execute(
                "SELECT COUNT(*) FROM graph_edges WHERE relationship = 'POSTS_FOR'"
            ).fetchone()[0]
            logger.info("  Built %d JournalEntry→BillingDocument edges (POSTS_FOR)", count)
        except Exception as exc:
            logger.error("JournalEntry→BillingDocument edge insert failed: %s", exc)

    # JournalEntry --CUSTOMER_LEDGER--> Customer
    if has("journal_entry_items_accounts_receivable"):
        _insert_edges(db, "JournalEntry", "accountingDocument",
                      "Customer", "customer",
                      "CUSTOMER_LEDGER", "journal_entry_items_accounts_receivable",
                      "customer IS NOT NULL AND customer != ''")

    db.commit()

    node_count = db.execute("SELECT COUNT(*) FROM graph_nodes").fetchone()[0]
    edge_count = db.execute("SELECT COUNT(*) FROM graph_edges").fetchone()[0]
    logger.info("Graph built: %d nodes, %d edges", node_count, edge_count)


if __name__ == "__main__":
    import logging as _logging
    from database.ingest import ingest_all
    from database.connection import Database
    _logging.basicConfig(level=_logging.INFO, format="%(levelname)s  %(message)s")
    ingest_all()
    db = Database.get()
    build_graph(db)

