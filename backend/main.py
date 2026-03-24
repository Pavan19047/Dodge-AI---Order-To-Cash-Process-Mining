"""
main.py — FastAPI application entry point for Dodge AI.

Startup sequence:
1. Ingest CSV files from data/ into DuckDB (if not already done)
2. Build the graph adjacency tables (if empty)
3. Start the REST API

Run with:
    uvicorn main:app --reload --port 8000
"""

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import ALLOWED_ORIGINS
from database.connection import Database
from database.ingest import ingest_all
from database.graph_builder import build_graph
from graph.routes import router as graph_router
from chat.routes import router as chat_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Startup / shutdown lifecycle
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    db = Database.get()

    # Ingest CSVs
    logger.info("Starting data ingestion…")
    table_cols = ingest_all()

    if table_cols:
        # Check if graph is already populated
        node_count = db.execute("SELECT COUNT(*) FROM graph_nodes").fetchone()[0]
        if node_count == 0:
            logger.info("Graph is empty — building…")
            build_graph(db)
        else:
            logger.info("Graph already populated (%d nodes) — skipping rebuild.", node_count)
    else:
        logger.warning(
            "No CSV files found in data/. "
            "Place your CSV files in backend/data/ and restart."
        )

    yield  # Application runs here

    logger.info("Shutting down…")


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Dodge AI — Order-to-Cash Process Mining",
    version="1.0.0",
    description="Graph-based O2C analytics with LLM-powered natural language querying.",
    lifespan=lifespan,
)

# CORS — allow the frontend origin
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(graph_router)
app.include_router(chat_router)


@app.get("/")
def root():
    return {
        "service": "Dodge AI — Order-to-Cash Process Mining",
        "version": "1.0.0",
        "docs": "/docs",
    }


@app.get("/health")
def health():
    db = Database.get()
    try:
        node_count = db.execute("SELECT COUNT(*) FROM graph_nodes").fetchone()[0]
        edge_count = db.execute("SELECT COUNT(*) FROM graph_edges").fetchone()[0]
        return {"status": "ok", "nodes": node_count, "edges": edge_count}
    except Exception as exc:
        return {"status": "error", "detail": str(exc)}
