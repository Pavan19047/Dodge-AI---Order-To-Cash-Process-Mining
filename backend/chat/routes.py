"""
Chat API routes — POST /api/chat
"""

import logging
from typing import Any, Optional

import pandas as pd
from fastapi import APIRouter
from pydantic import BaseModel

from chat.query_generator import generate_intent_and_sql
from chat.executor import execute_query, extract_entity_ids
from chat.response_formatter import format_response
from chat.guardrails import fast_domain_check
from chat.prompts import OFF_TOPIC_RESPONSE, SQL_ERROR_RESPONSE
from database.connection import Database
from database.ingest import get_schema_context_slim

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/chat", tags=["chat"])


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------

class HistoryItem(BaseModel):
    role: str        # "user" | "assistant"
    content: str


class ChatRequest(BaseModel):
    message: str
    history: list[HistoryItem] = []


class HighlightedEntity(BaseModel):
    type: str
    id: str


class ChatResponse(BaseModel):
    message: str
    intent: Optional[str] = None
    sql: Optional[str] = None
    data: Optional[list[dict[str, Any]]] = None
    highlighted_entities: list[HighlightedEntity] = []


# ---------------------------------------------------------------------------
# Route
# ---------------------------------------------------------------------------

@router.post("", response_model=ChatResponse)
async def chat(request: ChatRequest):
    query = request.message.strip()
    if not query or len(query) < 3:
        return ChatResponse(message="Please enter a question.")

    # Fast pre-filter: reject obviously off-topic queries without hitting the LLM
    if not fast_domain_check(query):
        return ChatResponse(message=OFF_TOPIC_RESPONSE, intent="OFF_TOPIC")

    db = Database.get()

    # ---- Stage 1+2 combined: intent classification + SQL generation ----
    schema = get_schema_context_slim(db)
    history = [item.model_dump() for item in request.history]
    intent, sql = await generate_intent_and_sql(query, schema, history=history)
    logger.info("Intent=%s | SQL=%s", intent, (sql or "")[:80])

    if intent == "OFF_TOPIC":
        return ChatResponse(message=OFF_TOPIC_RESPONSE, intent=intent)

    if not sql:
        return ChatResponse(message=SQL_ERROR_RESPONSE, intent=intent, sql=None)

    # ---- Stage 3: Execute ----
    df, error = execute_query(db, sql)

    if error:
        logger.warning("Query execution error: %s", error)
        return ChatResponse(message=SQL_ERROR_RESPONSE, intent=intent, sql=sql)

    # ---- Stage 4: Format response ----
    natural_response = await format_response(query, sql, df, intent=intent)

    # ---- Extract highlighted entities ----
    highlighted = []
    if df is not None and not df.empty:
        raw_entities = extract_entity_ids(df)
        highlighted = [HighlightedEntity(type=e["type"], id=e["id"]) for e in raw_entities]

    # Convert dataframe to JSON-serialisable list of dicts
    data = None
    if df is not None and not df.empty:
        records = []
        for _, row in df.iterrows():
            record = {}
            for k, v in row.items():
                if pd.isna(v):
                    record[k] = None
                elif hasattr(v, "item"):
                    record[k] = v.item()
                else:
                    record[k] = str(v)
            records.append(record)
        data = records

    return ChatResponse(
        message=natural_response,
        intent=intent,
        sql=sql,
        data=data,
        highlighted_entities=highlighted,
    )
