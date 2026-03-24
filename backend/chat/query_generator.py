"""
Chat query pipeline — single Gemini call returns both intent and SQL.
"""

import asyncio
import json
import logging
import re

import google.generativeai as genai

from config import GEMINI_API_KEY, GEMINI_MODEL
from chat.intent_classifier import IntentType
from chat.prompts import ONE_SHOT_PROMPT

logger = logging.getLogger(__name__)

_model = None


def _get_model():
    global _model
    if _model is None:
        genai.configure(api_key=GEMINI_API_KEY)
        _model = genai.GenerativeModel(GEMINI_MODEL)
    return _model


def _extract_json(text: str) -> dict:
    """Extract the first JSON object from a possibly noisy LLM response."""
    text = text.strip()
    # Strip markdown fences if present
    text = re.sub(r"^```[a-z]*\n?", "", text)
    text = re.sub(r"\n?```$", "", text)
    # Find the first {...} block
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        return json.loads(match.group())
    raise ValueError(f"No JSON object found in: {text!r}")


def _strip_markdown_sql(sql: str) -> str:
    sql = sql.strip()
    for fence in ("```sql", "```duckdb", "```"):
        if sql.startswith(fence):
            sql = sql[len(fence):]
    if sql.endswith("```"):
        sql = sql[:-3]
    return sql.strip()


class QuotaExhaustedError(Exception):
    """Raised when the Gemini API key has no remaining quota."""


async def _call_with_retry(model, prompt: str, generation_config: dict, timeout: int) -> str:
    """Call Gemini with up to 3 retries on 429 rate-limit errors."""
    delays = [6, 15, 30]
    for attempt, delay in enumerate(delays, 1):
        try:
            response = await asyncio.wait_for(
                model.generate_content_async(prompt, generation_config=generation_config),
                timeout=timeout,
            )
            return response.text
        except asyncio.TimeoutError:
            raise
        except Exception as exc:
            exc_str = str(exc)
            # Daily/project quota exhausted (limit=0) — no point retrying
            if ("limit: 0" in exc_str or "RESOURCE_EXHAUSTED" in exc_str) and (
                "PerDay" in exc_str or "limit: 0" in exc_str
            ):
                raise QuotaExhaustedError("Gemini API quota exhausted") from exc
            if "429" in exc_str and attempt < len(delays):
                logger.warning("Rate limited (429), retrying in %ds (attempt %d)…", delay, attempt)
                await asyncio.sleep(delay)
            else:
                raise
    raise RuntimeError("Max retries exceeded")


def _format_history_block(history: list[dict]) -> str:
    """Format conversation history as a prompt block, or empty string if none."""
    if not history:
        return ""
    lines = ["CONVERSATION HISTORY (most recent last):"]
    for item in history[-6:]:  # cap at 6 turns
        role = "User" if item.get("role") == "user" else "Assistant"
        lines.append(f"  {role}: {item.get('content', '')[:300]}")
    lines.append("")  # blank line before current query
    return "\n".join(lines) + "\n"


async def generate_intent_and_sql(
    query: str, schema: str, history: list[dict] | None = None
) -> tuple[IntentType, str | None]:
    """
    Single Gemini call that returns both intent and SQL.
    Falls back to rule_engine on QuotaExhaustedError or missing API key.
    """
    from chat.rule_engine import classify_intent, generate_sql  # local import to avoid circular

    history = history or []

    if not GEMINI_API_KEY:
        logger.info("No Gemini API key configured — using rule-based fallback.")
        intent = classify_intent(query)
        sql = generate_sql(intent, query)
        return intent, sql  # type: ignore[return-value]

    history_block = _format_history_block(history)
    prompt = ONE_SHOT_PROMPT.format(schema=schema, query=query, history_block=history_block)
    try:
        model = _get_model()
        text = await _call_with_retry(
            model, prompt,
            generation_config={"temperature": 0.1, "max_output_tokens": 1024},
            timeout=30,
        )
        parsed = _extract_json(text)
        intent: IntentType = parsed.get("intent", "AGGREGATION").strip().upper()  # type: ignore[assignment]
        sql_raw = parsed.get("sql", "") or ""
        sql = _strip_markdown_sql(sql_raw) or None
        logger.debug("ONE_SHOT intent=%s sql=%s", intent, (sql or "")[:120])
        return intent, sql
    except QuotaExhaustedError:
        logger.warning("Gemini quota exhausted — switching to rule-based fallback.")
        intent = classify_intent(query)
        sql = generate_sql(intent, query)
        return intent, sql  # type: ignore[return-value]
    except asyncio.TimeoutError:
        logger.error("Gemini call timed out (30s) — using rule-based fallback.")
        intent = classify_intent(query)
        sql = generate_sql(intent, query)
        return intent, sql  # type: ignore[return-value]
    except Exception as exc:
        logger.error("generate_intent_and_sql error: %s — using rule-based fallback.", exc)
        intent = classify_intent(query)
        sql = generate_sql(intent, query)
        return intent, sql  # type: ignore[return-value]

