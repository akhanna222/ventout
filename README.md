# Listener AI Prototype Plan

This repository outlines a blueprint for building "Listener AI": a calming voice companion that supports async voice notes and low-latency realtime calls using OpenAI's audio capabilities. It includes a safety-first interaction model, backend scaffolding, and a simple UI concept featuring a responsive mood orb.

## Features at a Glance
- **Voice notes (async):** Upload an audio clip and receive an AI-generated audio response.
- **Realtime conversations:** Stream microphone audio and receive near-live AI speech responses.
- **Safety-first behavior:** Harm/rage screening, escalation handling, and cooldowns.
- **Authentication:** Email/password with JWT sessions; room for SSO later.
- **Calming UI:** A minimal interface with a "mood orb" that changes color/shape based on emotional intensity.

## High-Level Architecture
```
listener-ai/
  backend/
    app/
      main.py          # FastAPI app (REST + WebSocket)
      deps.py          # Auth + DB dependencies
      schemas.py       # Pydantic models
      services/
        audio.py       # STT/TTS helpers
        safety.py      # Harm/rage checks
        sessions.py    # State machine + response shaping
    requirements.txt
  frontend/
    src/
      App.jsx         # UI shell + mood orb component
      api.js          # Client calls for voice notes & tokens
    package.json      # React + Web Audio/WebRTC deps
```

### Data Stores
- **Postgres:** users, sessions, message history, safety flags. JWT auth now uses a `users` table via async SQLAlchemy.
- **Redis:** recommended for ephemeral session state, rate limits, cooldown timers. The prototype uses an in-memory cooldown cache.
- **Object storage (S3/GCS):** optional raw audio if user opts in.

### OpenAI APIs Used
- **Transcription:** `audio/transcriptions` with `gpt-4o-mini-transcribe`.
- **Text-to-speech:** `audio/speech` with `gpt-4o-mini-tts` voices and style instructions.
- **Realtime speech:** OpenAI Realtime API over WebRTC/WebSocket for low latency.

## Interaction Rules (System Prompt)
Use this as the system prompt for both modes:

> You are "Listener", a calm, non-confrontational voice companion. Primary goal: reduce emotional intensity and prevent harm. Default behavior: brief acknowledgements, reflections, and questions that invite safe expression. Never debate, never shame, never escalate. Validate feelings without endorsing harmful actions. Ask permission before giving advice or coaching. Keep responses concise unless the user asks for detail. If user expresses intent to harm self/others or imminent danger: switch to safety response, encourage contacting local emergency services / trusted person, and keep the user grounded. When the user is looping or ruminating: gently interrupt and offer a 60-second reset (breathing/grounding) or a structured next step. Maintain a warm tone; speak like a steady friend.

Suggested developer prompt additions:
- **Mode=VENT:** 1–2 sentences max, no advice unless asked.
- **Mode=REFLECT:** paraphrase + label feeling + validate.
- **Mode=REGULATE:** one exercise + wait.
- **Mode=PLAN:** one concrete next step + draft message option.

## Safety Layer (non-negotiable)
- Intent check at session start: "Just listen, or help calm down?"
- Harm classifier + keyword guardrails (self-harm, violence, revenge, harassment).
- Boundaries: refuse revenge/violence; redirect to calming + safe action.
- Rate limiting + cooldowns for escalating loops; block abusive bursts.
- High-risk path: offer emergency contact, helpline, or human handoff.

## Backend: FastAPI Skeleton
Key behaviors:
- Auth via JWT (login/signup endpoints).
- `/voice-note`: accepts an audio file, transcribes, runs state logic, returns AI audio.
- `/realtime/token`: creates a short-lived token/config so the client can connect to the Realtime API.
- Safety filters wrap both modes.

Run locally:
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r backend/requirements.txt
uvicorn backend.app.main:app --reload
```

### EC2 one-shot bootstrap (interactive)
Use the helper script to clone the repo, prompt for keys, pick open ports, install deps, and start both servers in nohup sessions. It prefers security-group-open ports (80/443/3000/8000) and will prompt again if a port is already bound on the host.

```bash
# From a fresh EC2 host
chmod +x scripts/ec2_bootstrap.sh
./scripts/ec2_bootstrap.sh
```

Prompts you will see:
- Git clone URL + branch/tag.
- Install directory (default `~/listener-ai`).
- Backend + frontend ports (script suggests a free port and re-prompts if busy).
- OpenAI API key, JWT secret, Postgres URL (or blank for sqlite dev), optional S3 bucket/region/prefix.

Notes:
- The script writes `backend/.env`, installs Python/Node, builds the frontend, and starts uvicorn + Vite preview with nohup logs (`backend.log`, `frontend.log`).
- Ensure your EC2 security group allows inbound access to the ports you choose (default open ones listed above). If all listed ports are in use, pick another free port and add a rule.

Environment variables (example):
```
OPENAI_API_KEY=...
JWT_SECRET=super-secret
POSTGRES_URL=postgresql+psycopg://user:pass@localhost:5432/listener
REDIS_URL=redis://localhost:6379/0
OPENAI_REALTIME_MODEL=gpt-4o-realtime-preview
S3_BUCKET=listener-audio
S3_REGION=us-east-1
S3_PREFIX=voice-notes
```

## Frontend: Minimal React Concept
- WebAudio/WebRTC for mic capture.
- Upload flow for voice notes (m4a/mp3/wav).
- Mood orb component animates color/shape based on detected intensity (low → soft teal circle; medium → amber oval; high → red spiky blob).
- Safety UX: shows cooldown timers, quick helpline button, consent toggle for storing audio.

Run locally:
```bash
cd frontend
npm install
npm run dev
```

## Quick test on Google Colab
Colab works well for short backend checks. The helper script installs dependencies, writes a minimal `.env`, and can open a Cloudflare tunnel so you can hit FastAPI from your browser.

1. In a new Colab notebook cell, set your key and clone:
   ```python
   import os, subprocess, textwrap
   os.environ["OPENAI_API_KEY"] = "sk-..."  # required
   subprocess.run("git clone https://github.com/<your-fork>/ventout.git", shell=True, check=True)
   %cd ventout
   ```
2. Run the bootstrap script (defaults to port 8000, sqlite DB). Add `--with-tunnel` to expose a public URL via Cloudflare in another cell tab.
   ```bash
   !bash scripts/colab_quickstart.sh --with-tunnel
   ```
3. Watch logs for the tunnel URL (in `backend/colab_tunnel.log`) and backend status (`backend/colab_backend.log`).
4. Try auth + voice note from Colab using `requests` (replace `TUNNEL_URL` if using a tunnel):
   ```python
   import requests, base64

   base = "http://localhost:8000"  # or the tunnel URL
   token = requests.post(f"{base}/auth/register", json={"email": "test@example.com", "password": "demo"}).json()["access_token"]
   headers = {"Authorization": f"Bearer {token}"}

   # Send a tiny silence wav for a smoke test
   wav = base64.b64decode("UklGRiQAAABXQVZFZm10IBAAAAABAAEAQB8AAIA+AAACABAAZGF0YQAAAAA=")
   resp = requests.post(f"{base}/voice-note", files={"file": ("test.wav", wav, "audio/wav")}, headers=headers)
   resp.json()
   ```

Notes:
- The script uses sqlite by default; set `POSTGRES_URL` before running if you need Postgres.
- The frontend is not started in Colab. You can still hit the FastAPI endpoints via the tunnel for API-level checks.
- If ports are busy, rerun with `PORT=9000 bash scripts/colab_quickstart.sh --with-tunnel`.

## What to build next
1. Wire JWT auth to Postgres. ✅
2. Swap stub safety classifier with a real model + keyword list. ✅ (LLM + keywords)
3. Add S3 upload helper if storing raw audio with consent. ✅
4. Implement cooldown timers + UI hints. ✅
5. Add WebRTC transport for Realtime API when browser support is present. ✅ (client stub)
