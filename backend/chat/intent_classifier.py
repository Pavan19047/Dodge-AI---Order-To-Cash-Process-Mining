"""
Stage 1: Intent classification using Gemini.
"""

import logging
from typing import Literal

import google.generativeai as genai

from config import GEMINI_API_KEY, GEMINI_MODEL
from chat.prompts import INTENT_CLASSIFICATION_PROMPT

logger = logging.getLogger(__name__)

VALID_INTENTS = {
    "TRACE_FLOW",
    "AGGREGATION",
    "ANOMALY_DETECTION",
    "ENTITY_LOOKUP",
    "RELATIONSHIP_QUERY",
    "OFF_TOPIC",
}

IntentType = Literal[
    "TRACE_FLOW",
    "AGGREGATION",
    "ANOMALY_DETECTION",
    "ENTITY_LOOKUP",
    "RELATIONSHIP_QUERY",
    "OFF_TOPIC",
]

_model = None


def _get_model():
    global _model
    if _model is None:
        genai.configure(api_key=GEMINI_API_KEY)
        _model = genai.GenerativeModel(GEMINI_MODEL)
    return _model


async def classify_intent(query: str) -> IntentType:
    """
    Call Gemini to classify query intent.
    Returns one of the VALID_INTENTS strings.
    Falls back to AGGREGATION on failure so we still attempt a response.
    """
    prompt = INTENT_CLASSIFICATION_PROMPT.format(query=query)
    try:
        model = _get_model()
        response = await model.generate_content_async(
            prompt,
            generation_config={"temperature": 0, "max_output_tokens": 20},
            request_options={"timeout": 20},
        )
        raw = response.text.strip().upper()
        # Clean up any stray punctuation
        for intent in VALID_INTENTS:
            if intent in raw:
                return intent  # type: ignore[return-value]
        logger.warning("Unrecognised intent response '%s', defaulting to AGGREGATION", raw)
        return "AGGREGATION"
    except Exception as exc:
        logger.error("Intent classification error: %s", exc)
        return "AGGREGATION"
