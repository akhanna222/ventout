import base64
import os
import time
import uuid
from datetime import datetime, timedelta
from typing import Any

import jwt

SYSTEM_PROMPT = os.getenv("LISTENER_SYSTEM_PROMPT", "You are Listener, a calm companion.")
JWT_SECRET = os.getenv("JWT_SECRET", "change-me")
JWT_ALG = "HS256"
REALTIME_MODEL = os.getenv("OPENAI_REALTIME_MODEL", "gpt-4o-realtime-preview")
COOLDOWN_SECONDS = int(os.getenv("COOLDOWN_SECONDS", "60"))

_cooldowns: dict[str, float] = {}


def create_jwt_for_user(user: Any) -> str:
    payload = {
        "sub": str(user.email),
        "uid": int(user.id),
        "exp": datetime.utcnow() + timedelta(hours=12),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALG)


def decode_jwt(token: str) -> dict[str, Any] | None:
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALG])
        return {"email": payload.get("sub"), "uid": payload.get("uid")}
    except Exception:
        return None


def new_session(user_email: str) -> str:
    return str(uuid.uuid4())


def generate_reply(transcript: str) -> str:
    # Placeholder: real implementation would call OpenAI Chat/Realtime
    return "I hear you. I'm here with you."


def issue_realtime_token(user_email: str) -> str:
    # In production, mint a server-authorized token for OpenAI Realtime
    payload = {
        "sub": user_email,
        "model": REALTIME_MODEL,
        "exp": int(time.time()) + 600,
        "scope": "realtime:client",
    }
    return base64.b64encode(jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALG).encode()).decode()


def apply_cooldown(email: str, level: str) -> float:
    if level in {"blocked", "elevated"}:
        until = time.time() + COOLDOWN_SECONDS
        _cooldowns[email] = until
        return until
    return 0


def cooldown_remaining(email: str) -> int:
    expires_at = _cooldowns.get(email)
    if not expires_at:
        return 0
    remaining = int(expires_at - time.time())
    if remaining <= 0:
        _cooldowns.pop(email, None)
        return 0
    return remaining
