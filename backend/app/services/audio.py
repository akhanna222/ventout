import base64
import os
from io import BytesIO
from typing import Optional

import httpx

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "demo-key")
TRANSCRIBE_MODEL = os.getenv("OPENAI_TRANSCRIBE_MODEL", "gpt-4o-mini-transcribe")
TTS_MODEL = os.getenv("OPENAI_TTS_MODEL", "gpt-4o-mini-tts")
TTS_VOICE = os.getenv("OPENAI_TTS_VOICE", "alloy")
TTS_STYLE = os.getenv("OPENAI_TTS_STYLE", "calm")


async def transcribe_bytes(payload: bytes, filename: Optional[str] = None) -> str:
    """Send audio to OpenAI transcription. Returns text transcript."""
    if not payload:
        return ""

    if not OPENAI_API_KEY:
        return "(transcript placeholder)"

    files = {"file": (filename or "voice_note.wav", payload, "application/octet-stream")}
    data = {"model": TRANSCRIBE_MODEL}
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            "https://api.openai.com/v1/audio/transcriptions",
            headers={"Authorization": f"Bearer {OPENAI_API_KEY}"},
            data=data,
            files=files,
        )
    resp.raise_for_status()
    return resp.json().get("text", "")


async def say(text: str) -> str:
    """Generate TTS audio and return base64-encoded bytes."""
    if not OPENAI_API_KEY:
        fake_audio = BytesIO()
        fake_audio.write(text.encode())
        return base64.b64encode(fake_audio.getvalue()).decode()

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            "https://api.openai.com/v1/audio/speech",
            headers={"Authorization": f"Bearer {OPENAI_API_KEY}"},
            json={"model": TTS_MODEL, "voice": TTS_VOICE, "input": text, "style": TTS_STYLE},
        )
    resp.raise_for_status()
    return base64.b64encode(resp.content).decode()
