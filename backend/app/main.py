from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel

from .services import audio, auth, safety, sessions, storage
from .services.db import User, get_session, init_db

app = FastAPI(title="Listener AI", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


class AuthPayload(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class VoiceNoteResponse(BaseModel):
    session_id: str
    audio_url: str | None = None
    audio_bytes_b64: str | None = None
    safety_level: str
    cooldown_seconds: int | None = None
    safety_reasons: list[str] | None = None
    stored_audio_url: str | None = None


@app.post("/auth/login", response_model=TokenResponse)
async def login(payload: AuthPayload, db_session=Depends(get_session)):
    user: User | None = await auth.get_user_by_email(db_session, payload.email)
    if not user or not auth.verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = sessions.create_jwt_for_user(user)
    return TokenResponse(access_token=token)


@app.post("/auth/register", response_model=TokenResponse)
async def register(payload: AuthPayload, db_session=Depends(get_session)):
    existing = await auth.get_user_by_email(db_session, payload.email)
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    user = await auth.create_user(db_session, payload.email, payload.password)
    token = sessions.create_jwt_for_user(user)
    return TokenResponse(access_token=token)


@app.post("/voice-note", response_model=VoiceNoteResponse)
async def voice_note(
    file: UploadFile = File(...),
    store_raw: bool = Form(False),
    token: str = Depends(oauth2_scheme),
    db_session=Depends(get_session),
):
    claims = sessions.decode_jwt(token)
    if not claims:
        raise HTTPException(status_code=401, detail="Invalid token")

    user: User | None = await auth.get_user_by_id(db_session, claims["uid"])
    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    remaining = sessions.cooldown_remaining(user.email)
    if remaining:
        response_audio = await audio.say(
            "We're taking a short pause to keep things safe. Let's breathe together, then you can try again."
        )
        return VoiceNoteResponse(
            session_id=sessions.new_session(user_email=user.email),
            audio_bytes_b64=response_audio,
            safety_level="elevated",
            cooldown_seconds=remaining,
        )

    payload = await file.read()
    stored_url = None
    if store_raw and payload:
        stored_url = storage.upload_raw_audio(user.id, payload, file.content_type)

    transcript = await audio.transcribe_bytes(payload, filename=file.filename)
    safety_level, reasons = await safety.classify(transcript)
    sessions.apply_cooldown(user.email, safety_level)

    if safety.is_blocked(safety_level):
        response_audio = await audio.say(
            "I hear you're struggling. For safety, let's pause and reach out to someone you trust or a local helpline."
        )
        return VoiceNoteResponse(
            session_id=sessions.new_session(user_email=user.email),
            audio_bytes_b64=response_audio,
            safety_level=safety_level,
            cooldown_seconds=sessions.cooldown_remaining(user.email),
            safety_reasons=reasons,
            stored_audio_url=stored_url,
        )

    reply_text = sessions.generate_reply(transcript)
    response_audio = await audio.say(reply_text)
    return VoiceNoteResponse(
        session_id=sessions.new_session(user_email=user.email),
        audio_bytes_b64=response_audio,
        safety_level=safety_level,
        cooldown_seconds=sessions.cooldown_remaining(user.email),
        safety_reasons=reasons,
        stored_audio_url=stored_url,
    )


@app.get("/realtime/token", response_model=TokenResponse)
async def realtime_token(token: str = Depends(oauth2_scheme)):
    claims = sessions.decode_jwt(token)
    if not claims:
        raise HTTPException(status_code=401, detail="Invalid token")
    realtime_token = sessions.issue_realtime_token(claims["email"])
    return TokenResponse(access_token=realtime_token)


@app.get("/health")
async def health():
    return {"ok": True}


@app.on_event("startup")
async def on_start():
    await init_db()
