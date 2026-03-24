"""
All LLM prompt templates in one place.
"""

# ---------------------------------------------------------------------------
# Combined intent + SQL generation (single LLM call)
# ---------------------------------------------------------------------------

ONE_SHOT_PROMPT = """\
You are an AI analyst for an SAP Order-to-Cash system backed by DuckDB.

DATABASE SCHEMA (table: columns):
{schema}

INTENT CATEGORIES:
- TRACE_FLOW         : trace the full lifecycle of a document (use graph_edges + recursive CTE)
- AGGREGATION        : counts, totals, rankings, averages (GROUP BY / ORDER BY)
- ANOMALY_DETECTION  : find broken or incomplete flows (LEFT JOIN / NOT EXISTS)
- ENTITY_LOOKUP      : details about a specific entity by ID
- RELATIONSHIP_QUERY : which entities are connected to what
- OFF_TOPIC          : not related to order-to-cash data

{history_block}User query: {query}

Respond with ONLY a JSON object — no markdown, no explanation:
{{"intent": "<INTENT>", "sql": "<single DuckDB SELECT or empty string if OFF_TOPIC>"}}

SQL rules:
- One SELECT statement only; no DDL/DML
- Always LIMIT to at most 50 rows
- Use meaningful column aliases
- If OFF_TOPIC set sql to ""
"""


# ---------------------------------------------------------------------------
# Stage 1 (legacy, kept for backward compatibility)
# ---------------------------------------------------------------------------

INTENT_CLASSIFICATION_PROMPT = """\
The system contains data about: Sales Orders, Deliveries, Billing Documents,
Journal Entries, Customers, Materials, and Plants.

Classify the user's query into EXACTLY ONE of these categories:
- TRACE_FLOW         : User wants to trace the lifecycle of a specific document/entity
- AGGREGATION        : User wants counts, totals, rankings, or statistical summaries
- ANOMALY_DETECTION  : User wants to find broken flows, missing links, or incomplete processes
- ENTITY_LOOKUP      : User wants details about a specific entity by ID
- RELATIONSHIP_QUERY : User wants to know what entities are connected to what
- OFF_TOPIC          : Query is NOT related to order-to-cash business data

Respond with ONLY the category name — nothing else, no explanation, no punctuation.

User query: {query}
"""

# ---------------------------------------------------------------------------
# Stage 2: SQL generation — one template per intent
# ---------------------------------------------------------------------------

TRACE_FLOW_PROMPT = """\
You are a SQL expert for an Order-to-Cash system using DuckDB (version 0.10+).

DATABASE SCHEMA:
{schema}

GRAPH ADJACENCY TABLE:
  graph_edges(source_type VARCHAR, source_id VARCHAR, target_type VARCHAR, target_id VARCHAR, relationship VARCHAR)

The user wants to trace the full Order-to-Cash lifecycle of a document.
The canonical flow is: SalesOrder → Delivery → BillingDocument → JournalEntry

Instructions:
1. Identify the entity type and ID from the user query.
2. Start from that entity in graph_edges and use a RECURSIVE CTE to traverse all connected nodes.
3. Join back to the actual data tables to return meaningful business fields.
4. Return all entities in the chain with their key properties.
5. Limit to 50 rows.

User query: {query}

Respond with ONLY valid DuckDB SQL. No explanation. No markdown code fences.
"""

AGGREGATION_PROMPT = """\
You are a SQL expert for an Order-to-Cash system using DuckDB (version 0.10+).

DATABASE SCHEMA:
{schema}

Generate a SQL query to answer the user's aggregation question.
- Use appropriate GROUP BY, COUNT, SUM, AVG, ORDER BY, LIMIT clauses.
- Always include meaningful column aliases.
- LIMIT the result to at most 20 rows.
- Prefer readable output with descriptive column names.

User query: {query}

Respond with ONLY valid DuckDB SQL. No explanation. No markdown code fences.
"""

ANOMALY_DETECTION_PROMPT = """\
You are a SQL expert for an Order-to-Cash system using DuckDB (version 0.10+).

DATABASE SCHEMA:
{schema}

GRAPH ADJACENCY TABLE:
  graph_edges(source_type VARCHAR, source_id VARCHAR, target_type VARCHAR, target_id VARCHAR, relationship VARCHAR)

The user wants to find broken or incomplete Order-to-Cash flows.

Common anomaly patterns to detect:
- Sales orders with no delivery  (no row in graph_edges where source_type='SalesOrder' and target_type='Delivery')
- Deliveries with no billing document
- Billing documents with no journal entry
- Items with quantity mismatches between order and delivery
- Documents referencing non-existent parent entities

Use LEFT JOINs or NOT EXISTS sub-queries to find these gaps.
LIMIT the result to 50 rows.

User query: {query}

Respond with ONLY valid DuckDB SQL. No explanation. No markdown code fences.
"""

ENTITY_LOOKUP_PROMPT = """\
You are a SQL expert for an Order-to-Cash system using DuckDB (version 0.10+).

DATABASE SCHEMA:
{schema}

The user wants details about a specific entity.
Return all relevant fields for that entity from the appropriate table.
If an ID is mentioned, filter by it.
LIMIT to 10 rows.

User query: {query}

Respond with ONLY valid DuckDB SQL. No explanation. No markdown code fences.
"""

RELATIONSHIP_QUERY_PROMPT = """\
You are a SQL expert for an Order-to-Cash system using DuckDB (version 0.10+).

DATABASE SCHEMA:
{schema}

GRAPH ADJACENCY TABLE:
  graph_edges(source_type VARCHAR, source_id VARCHAR, target_type VARCHAR, target_id VARCHAR, relationship VARCHAR)

The user wants to know what entities are connected to a given entity.
Query graph_edges and join to the graph_nodes or actual data tables to return
meaningful information about the related entities.
LIMIT to 50 rows.

User query: {query}

Respond with ONLY valid DuckDB SQL. No explanation. No markdown code fences.
"""

# ---------------------------------------------------------------------------
# Stage 3: Response formatting
# ---------------------------------------------------------------------------

RESPONSE_FORMAT_PROMPT = """\
You are a helpful business analyst for an Order-to-Cash system.

The user asked: {original_query}

SQL executed:
{sql}

Query results (JSON):
{results_json}

Instructions:
- Provide a clear, concise natural language answer based ONLY on these results.
- Reference specific document numbers, amounts, or names from the data.
- If the result set is empty, say so clearly and suggest possible reasons.
- Do NOT make up or infer information not present in the results.
- Format currency amounts nicely (commas for thousands, 2 decimal places).
- Format dates in a human-readable way if present.
- Keep the response under 200 words.
- Start directly with the answer — no preamble.
"""

OFF_TOPIC_RESPONSE = (
    "This system is designed to answer questions about the "
    "Order-to-Cash dataset only. I can help you with queries about "
    "sales orders, deliveries, billing documents, journal entries, "
    "customers, materials, and plants. Please ask a related question."
)

NO_RESULTS_RESPONSE = (
    "I couldn't find any data matching your query. "
    "This might be because:\n"
    "• The entity ID you specified doesn't exist in the dataset\n"
    "• The relationship you're asking about isn't present in the data\n"
    "• The filter conditions are too restrictive\n\n"
    "Try rephrasing your question or using a different entity ID."
)

SQL_ERROR_RESPONSE = (
    "I encountered an error while executing the query. "
    "Please try rephrasing your question. If you're looking for a specific "
    "entity, try including its document number or ID."
)
