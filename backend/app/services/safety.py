from __future__ import annotations

import json
import os
from typing import Tuple

import httpx

HARM_KEYWORDS = {
    "self_harm": [
        "suicide",
        "kill myself",
        "end it",
        "can't go on",
        "hurt myself",
        "jump off",
    ],
    "violence": [
        "hurt them",
        "revenge",
        "murder",
        "attack",
        "stab",
        "shoot",
        "get back at",
    ],
    "rage": ["smash", "destroy", "furious", "rage", "explode", "yell", "fume"],
}


SAFETY_LEVELS = ["ok", "elevated", "blocked"]
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
SAFETY_MODEL = os.getenv("OPENAI_SAFETY_MODEL", "gpt-4o-mini")


async def classify(transcript: str) -> Tuple[str, list[str]]:
    """Use a lightweight LLM check plus keyword scan to tag intensity."""
    level, reasons = _keyword_level(transcript)
    if not OPENAI_API_KEY:
        return level, reasons

    prompt = (
        "Rate this text as ok, elevated, or blocked based on self-harm/violence risk. "
        "Return a JSON object with level and reasons."
    )
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {OPENAI_API_KEY}"},
                json={
                    "model": SAFETY_MODEL,
                    "messages": [
                        {"role": "system", "content": prompt},
                        {
                            "role": "user",
                            "content": f"Text: {transcript}\nRespond with {{\"level\":..., \"reasons\":[...]}}",
                        },
                    ],
                    "response_format": {"type": "json_object"},
                },
            )
        resp.raise_for_status()
        content = resp.json()["choices"][0]["message"]["content"]
        data = json.loads(content)
        level_from_model = data.get("level", level)
        reasons_from_model = data.get("reasons", reasons)
        if level_from_model in SAFETY_LEVELS:
            return level_from_model, reasons_from_model
    except Exception:
        pass
    return level, reasons


def _keyword_level(transcript: str) -> Tuple[str, list[str]]:
    lowered = transcript.lower()
    reasons: list[str] = []
    if any(word in lowered for word in HARM_KEYWORDS["self_harm"]):
        reasons.append("self_harm")
    if any(word in lowered for word in HARM_KEYWORDS["violence"]):
        reasons.append("violence")
    if any(word in lowered for word in HARM_KEYWORDS["rage"]):
        reasons.append("rage")

    if any(reason in ["self_harm", "violence"] for reason in reasons):
        return "blocked", reasons
    if "rage" in reasons:
        return "elevated", reasons
    return "ok", reasons or ["no-flags"]


def is_blocked(level: str) -> bool:
    return level == "blocked"
