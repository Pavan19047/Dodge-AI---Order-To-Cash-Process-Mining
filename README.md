# Dodge AI — Order-to-Cash Process Mining

An interactive process mining tool for SAP-style Order-to-Cash data. Upload CSV exports, explore your business graph, and query it in plain English.

![Dodge AI](https://img.shields.io/badge/stack-FastAPI%20%7C%20DuckDB%20%7C%20Gemini%20%7C%20React%20%7C%20D3-blueviolet)

---

## Architecture

```
┌────────────────────────────────────────────────────────────┐
│                        Browser                             │
│                                                            │
│  ┌─────────────────────┐   ┌────────────────────────────┐  │
│  │   D3 Force Graph    │   │      Chat Panel            │  │
│  │   (65% width)       │   │   (Gemini-powered, 35%)    │  │
│  └────────────┬────────┘   └────────────┬───────────────┘  │
│               │ Axios                   │ Axios            │
└───────────────┼─────────────────────────┼──────────────────┘
                ▼                         ▼
┌──────────────────────────────────────────────────────────────┐
│                   FastAPI  (port 8000)                       │
│                                                              │
│   GET /api/graph/*    │    POST /api/chat                    │
│   ─────────────────   │    ──────────────────────────────    │
│   overview            │    1. Keyword guardrail (< 1 ms)     │
│   neighbors           │    2. Gemini one-shot:               │
│   trace               │       intent + SQL in one call       │
│   filter              │    3. validate + execute (DuckDB)    │
│   stats               │    4. Gemini NL response format      │
│                       │    (rule engine fallback for 2+4)    │
│                       │                                      │
│   ┌────────────────────────────────────────────┐            │
│   │              DuckDB  (embedded)             │            │
│   │                                             │            │
│   │   CSV tables (auto-ingested at startup)     │            │
│   │   graph_nodes  │  graph_edges               │            │
│   └────────────────────────────────────────────┘            │
└──────────────────────────────────────────────────────────────┘
```

### Why DuckDB instead of Neo4j?

- **Zero-config** embedded OLAP — no server to run, no driver to configure
- SAP CSV exports are relational; DuckDB reads them natively with `read_csv_auto()`
- Graph traversal is done via a **recursive CTE** over an adjacency table (`graph_edges`)  
  — SQL power with graph semantics
- `graph_nodes` and `graph_edges` are populated once at startup and re-built whenever new CSVs are detected

### Why a single one-shot LLM call?

Different question types require completely different query shapes:

| Intent | Query shape |
|--------|-------------|
| `TRACE_FLOW` | Recursive CTE BFS traversal |
| `AGGREGATION` | GROUP BY + ORDER BY |
| `ANOMALY_DETECTION` | LEFT JOIN / NOT EXISTS chains |
| `ENTITY_LOOKUP` | Direct row fetch |
| `RELATIONSHIP_QUERY` | JOIN across entity tables |

`ONE_SHOT_PROMPT` in `query_generator.py` sends the full schema, intent categories, and conversation history to Gemini in a **single call** that returns `{"intent": "...", "sql": "..."}` as JSON. This is cheaper and faster than two sequential API calls, and the model performs better when it can infer the correct SQL shape at the same time it identifies intent.

### Rule-based fallback engine

`chat/rule_engine.py` provides a complete zero-LLM path: regex-based intent classification + hard-coded SQL templates for all five intent types + natural-language summary builders. It activates automatically whenever Gemini is unavailable (missing key, quota exhausted, timeout). All SQL templates use the confirmed camelCase column names from the SAP JSONL exports.

### Three-layer guardrails

1. **Keyword pre-filter** (`chat/guardrails.py`): 40+ domain keywords + numeric ID pattern. Blocks obviously off-topic requests in < 1 ms before touching the LLM.
2. **LLM intent gate** (`chat/query_generator.py`): The one-shot Gemini call classifies any remaining off-topic queries as `OFF_TOPIC` and returns an empty SQL — the route handler short-circuits with a deflection message.
3. **SQL validator** (`chat/executor.py`): Regex blocklist — only `SELECT`/`WITH` allowed; `DROP, DELETE, UPDATE, INSERT, CREATE, EXEC, ATTACH, LOAD`, and SQL comment sequences are rejected before DuckDB execution.

---

## Project Structure

```
Dodge_AI_Task/
├── backend/
│   ├── config.py                 # paths, env vars, constants
│   ├── main.py                   # FastAPI app + lifespan startup
│   ├── requirements.txt
│   ├── .env.example
    └── data/                     # ← JSONL data files
│   │   └── sap-o2c-data/         # entity subdirectories
│   │   └── dodge.duckdb          # auto-created
│   ├── database/
│   │   ├── connection.py         # DuckDB singleton
│   │   ├── schema.py             # graph_nodes / graph_edges DDL
│   │   ├── ingest.py             # JSONL → DuckDB ingestion
│   │   └── graph_builder.py      # relational data → graph edges
│   ├── graph/
│   │   ├── models.py             # Pydantic models
│   │   ├── service.py            # BFS / filter / stats queries
│   │   └── routes.py             # GET /api/graph/* endpoints
│   └── chat/
│       ├── prompts.py            # all LLM prompt templates
│       ├── guardrails.py         # keyword pre-filter
│       ├── rule_engine.py        # zero-LLM fallback (intent + SQL + NL)
│       ├── query_generator.py    # one-shot Gemini: intent + SQL
│       ├── executor.py           # SQL validation + execution
│       ├── response_formatter.py # result → natural language
│       └── routes.py             # POST /api/chat
└── frontend/
    ├── index.html
    ├── vite.config.ts            # /api proxy → localhost:8000
    ├── tailwind.config.js        # custom dark theme
    └── src/
        ├── main.tsx
        ├── App.tsx               # 65/35 layout + wiring
        ├── index.css
        ├── types/index.ts        # shared TS interfaces
        ├── utils/
        │   ├── colors.ts         # entity type → hex colour
        │   └── graphLayout.ts    # D3 force simulation factory
        ├── services/api.ts       # Axios client
        ├── hooks/
        │   ├── useGraph.ts       # graph state + expand/filter
        │   └── useChat.ts        # chat history + send
        └── components/
            ├── GraphCanvas.tsx   # D3 force-directed graph
            ├── NodeDetailPanel.tsx
            ├── ChatPanel.tsx
            ├── ChatMessage.tsx   # SQL / data collapsible
            └── GraphControls.tsx # zoom controls + entity filter
```

---

## Setup

### Prerequisites

- Python 3.11+
- Node.js 18+
- A [Google AI Studio](https://aistudio.google.com/) API key

### 1 — Backend

```bash
cd backend

# Create and activate virtual environment
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env and set GEMINI_API_KEY=your-key-here
# (optional — the rule engine runs without a key)

# Start the server
uvicorn main:app --reload --port 8000
```

The server auto-ingests all JSONL files from `backend/data/sap-o2c-data/` on startup using DuckDB's `read_json_auto()`, then builds the graph adjacency table. Subsequent restarts skip re-ingestion if data is already loaded.

### 2 — Frontend

```bash
cd frontend

npm install        # or: pnpm install / yarn install
npm run dev        # starts Vite dev server on http://localhost:5173
```

Vite proxies all `/api/*` requests to `http://localhost:8000`.

---

## Data Format

Dodge AI ingests SAP Order-to-Cash data as **JSONL** files (one JSON object per line) stored under `backend/data/sap-o2c-data/<entity>/`. Key tables and their camelCase column names:

| DuckDB table | Key columns |
|---|---|
| `sales_order_headers` | `salesOrder`, `soldToParty`, `totalNetAmount`, `overallDeliveryStatus`, `creationDate` |
| `sales_order_items` | `salesOrder`, `salesOrderItem`, `material`, `requestedQuantity`, `netAmount`, `productionPlant` |
| `outbound_delivery_headers` | `deliveryDocument`, `shippingPoint`, `actualGoodsMovementDate`, `overallGoodsMovementStatus` |
| `outbound_delivery_items` | `deliveryDocument`, `deliveryDocumentItem`, `referenceSdDocument`, `plant` |
| `billing_document_headers` | `billingDocument`, `billingDocumentDate`, `totalNetAmount`, `soldToParty`, `accountingDocument` |
| `billing_document_items` | `billingDocument`, `billingDocumentItem`, `material`, `netAmount`, `referenceSdDocument` |
| `payments_accounts_receivable` | `accountingDocument`, `amountInTransactionCurrency`, `financialAccountType`, `customer`, `clearingDate` |
| `business_partners` | `businessPartner`, `customer`, `businessPartnerFullName` |
| `product_descriptions` | `product`, `productDescription` |

**Join chain**: `salesOrder` → `odi.referenceSdDocument` → `bdi.referenceSdDocument` → `bdh.billingDocument` → `bdh.accountingDocument` → `par.accountingDocument`

---

## API Reference

### Graph endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/graph/overview?limit=250` | Seed BFS from 30 SalesOrders |
| GET | `/api/graph/stats` | Node / edge counts by type |
| GET | `/api/graph/node/{type}/{id}` | Single node lookup |
| GET | `/api/graph/neighbors/{type}/{id}` | 1-hop neighbours |
| GET | `/api/graph/trace/{type}/{id}?depth=8` | Full BFS traversal |
| GET | `/api/graph/filter?types=SalesOrder,Delivery&limit=100` | Type-filtered subgraph |

### Chat endpoint

```
POST /api/chat
Content-Type: application/json

{
  "message": "Which customers have the highest outstanding value?",
  "history": [
    { "role": "user",      "content": "..." },
    { "role": "assistant", "content": "..." }
  ]
}
```

Response:
```json
{
  "message": "The top 5 customers by net order value are…",
  "intent": "AGGREGATION",
  "sql": "SELECT soldToParty, SUM(totalNetAmount) …",
  "data": [ { "soldToParty": "C1000", "total_revenue": 485000 } ],
  "highlighted_entities": [ { "type": "Customer", "id": "C1000" } ]
}
```

### Health check

```
GET /health
→ { "status": "ok", "nodes": 1842, "edges": 3204 }
```

---

## Deployment

### Docker (recommended)

```bash
# Copy and fill in your API key
cp backend/.env.example backend/.env
# Edit backend/.env: GEMINI_API_KEY=your-key-here  (optional)

docker-compose up --build
```

- Backend: `http://localhost:8000`
- Frontend: `http://localhost:80`
- DuckDB data is persisted via the `./backend/data` volume mount.

### Manual — Backend (Render / Railway)

1. Set `GEMINI_API_KEY`, `ALLOWED_ORIGINS` env vars in the platform dashboard
2. Build command: `pip install -r requirements.txt`
3. Start command: `uvicorn main:app --host 0.0.0.0 --port $PORT`
4. Persistent disk: mount to `/app/data` so the DuckDB file survives redeploys

### Manual — Frontend (Vercel)

1. Set `VITE_API_URL` build env var to your backend URL
2. Build command: `npm run build`
3. Output directory: `dist`

---

## Design Decisions

**No react-force-graph or vis.js** — D3 v7 directly. Libraries built on top of D3 limit customisability of per-node styling, highlight animations, and tooltip placement. The custom D3 integration in `GraphCanvas.tsx` uses `useEffect` for simulation lifecycle and SVG `<g>` groups for node drag/hover.

**DuckDB adjacency table** — `graph_nodes` and `graph_edges` mirror Neo4j semantics but live inside DuckDB. Graph traversal is a 4-hop BFS written as a recursive CTE. Statistical queries (aggregations, anomaly detection) benefit from DuckDB's columnar OLAP engine.

**Gemini `gemini-2.0-flash`** — fast and cost-effective for the one-shot intent+SQL call (`temperature=0.1`, 1024 token budget). The rule-based fallback (`rule_engine.py`) means the app is fully functional even without a Gemini key.

**Conversation memory** — the frontend sends the last 6 messages as `history` with every request. `query_generator.py` formats this as a `CONVERSATION HISTORY` block injected into the one-shot prompt, giving Gemini context for follow-up queries (e.g. "show me just the top 3" after a prior aggregation).

**Pydantic v2** — strict validation on all API request/response models. FastAPI automatically generates an OpenAPI schema at `/docs`.
