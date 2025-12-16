#!/usr/bin/env bash
set -euo pipefail

PORT="${PORT:-8000}"
TUNNEL=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --port)
      PORT="$2"
      shift 2
      ;;
    --with-tunnel)
      TUNNEL=1
      shift 1
      ;;
    *)
      echo "Unknown option: $1" >&2
      exit 1
      ;;
  esac
done

if [[ -z "${OPENAI_API_KEY:-}" ]]; then
  echo "OPENAI_API_KEY is required. Set it in the Colab cell, e.g. 'import os; os.environ[\"OPENAI_API_KEY\"] = \"sk-...\"'" >&2
  exit 1
fi

JWT_SECRET="${JWT_SECRET:-colab-secret}" 
POSTGRES_URL="${POSTGRES_URL:-sqlite+aiosqlite:///./listener.db}"

python -m venv .venv
source .venv/bin/activate
pip install --upgrade pip >/dev/null
pip install -r backend/requirements.txt >/dev/null

cat > backend/.env <<EOF_ENV
OPENAI_API_KEY=${OPENAI_API_KEY}
JWT_SECRET=${JWT_SECRET}
POSTGRES_URL=${POSTGRES_URL}
OPENAI_REALTIME_MODEL=${OPENAI_REALTIME_MODEL:-gpt-4o-realtime-preview}
EOF_ENV

nohup .venv/bin/uvicorn backend.app.main:app --host 0.0.0.0 --port "$PORT" > backend/colab_backend.log 2>&1 &
echo $! > backend/colab_backend.pid

echo "Backend started on port ${PORT} (pid $(cat backend/colab_backend.pid))."

tail -n 20 backend/colab_backend.log || true

if [[ "$TUNNEL" -eq 1 ]]; then
  if ! command -v cloudflared >/dev/null 2>&1; then
    pip install cloudflared >/dev/null
  fi
  nohup cloudflared tunnel --url "http://localhost:${PORT}" --no-autoupdate > backend/colab_tunnel.log 2>&1 &
  echo $! > backend/colab_tunnel.pid
  echo "Cloudflared tunnel starting (pid $(cat backend/colab_tunnel.pid)). Check backend/colab_tunnel.log for the public URL."
  tail -n 20 backend/colab_tunnel.log || true
else
  echo "No tunnel requested. Use --with-tunnel to get a public URL in Colab."
fi
