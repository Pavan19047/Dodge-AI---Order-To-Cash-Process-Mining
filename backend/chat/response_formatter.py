"""
Stage 3: Format raw SQL results into natural language using Gemini.
"""

import asyncio
import json
import logging

import google.generativeai as genai
import pandas as pd

from config import GEMINI_API_KEY, GEMINI_MODEL
from chat.prompts import NO_RESULTS_RESPONSE, RESPONSE_FORMAT_PROMPT

logger = logging.getLogger(__name__)

_model = None


def _get_model():
    global _model
    if _model is None:
        genai.configure(api_key=GEMINI_API_KEY)
        _model = genai.GenerativeModel(GEMINI_MODEL)
    return _model


def _df_to_json(df: pd.DataFrame, max_rows: int = 20) -> str:
    """Convert dataframe to a compact JSON string for the prompt."""
    try:
        subset = df.head(max_rows)
        # Convert to list of dicts, handling non-serialisable types
        records = []
        for _, row in subset.iterrows():
            record = {}
            for k, v in row.items():
                if pd.isna(v):
                    record[k] = None
                elif hasattr(v, "item"):  # numpy scalars
                    record[k] = v.item()
                else:
                    record[k] = str(v)
            records.append(record)
        return json.dumps(records, ensure_ascii=False, indent=None)
    except Exception as exc:
        logger.warning("Could not serialise results: %s", exc)
        return "[]"


async def format_response(
    original_query: str,
    sql: str,
    df: pd.DataFrame | None,
    intent: str = "AGGREGATION",
) -> str:
    """
    Call Gemini to turn raw results into a natural language answer.
    Falls back to rule_engine.build_summary() if LLM is unavailable.
    """
    from chat.rule_engine import build_summary  # local import to avoid circular

    if df is None or df.empty:
        return NO_RESULTS_RESPONSE

    if not GEMINI_API_KEY:
        return build_summary(intent, original_query, df)  # type: ignore[arg-type]

    results_json = _df_to_json(df)
    prompt = RESPONSE_FORMAT_PROMPT.format(
        original_query=original_query,
        sql=sql,
        results_json=results_json,
    )

    try:
        model = _get_model()
        delays = [6, 15]
        text = None
        for attempt, delay in enumerate(delays, 1):
            try:
                response = await asyncio.wait_for(
                    model.generate_content_async(
                        prompt,
                        generation_config={"temperature": 0.3, "max_output_tokens": 512},
                    ),
                    timeout=25,
                )
                text = response.text.strip()
                break
            except asyncio.TimeoutError:
                raise
            except Exception as exc:
                exc_str = str(exc)
                if ("limit: 0" in exc_str or "RESOURCE_EXHAUSTED" in exc_str):
                    logger.warning("Gemini quota exhausted in formatter — using rule-based summary.")
                    return build_summary(intent, original_query, df)  # type: ignore[arg-type]
                if "429" in exc_str and attempt < len(delays):
                    logger.warning("Rate limited (429), retrying in %ds…", delay)
                    await asyncio.sleep(delay)
                else:
                    raise
        return text or build_summary(intent, original_query, df)  # type: ignore[arg-type]
    except asyncio.TimeoutError:
        logger.error("Response formatter timed out (25s)")
        return build_summary(intent, original_query, df)  # type: ignore[arg-type]
    except Exception as exc:
        logger.error("Response formatting error: %s", exc)
        return build_summary(intent, original_query, df)  # type: ignore[arg-type]


def _fallback_summary(df) -> str:
    row_count = len(df)
    cols = list(df.columns)
    return (
        f"Query returned {row_count} row(s) with columns: {', '.join(cols)}.\n"
        "See the data table below for details."
    )
