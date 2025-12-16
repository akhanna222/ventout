#!/usr/bin/env bash
set -euo pipefail

# Listener AI EC2 bootstrapper
# - Clones the repo
# - Prompts for secrets (OpenAI, JWT, Postgres, optional S3)
# - Picks free backend/frontend ports (avoids ones already in use)
# - Installs runtime deps (Python, Node, git)
# - Installs backend/frontend dependencies
# - Writes backend/.env
# - Starts backend (uvicorn) and frontend (Vite preview) with nohup

INFO_COLOR="\033[1;36m"
WARN_COLOR="\033[1;33m"
ERR_COLOR="\033[1;31m"
RESET_COLOR="\033[0m"

log() { echo -e "${INFO_COLOR}[*]${RESET_COLOR} $1"; }
warn() { echo -e "${WARN_COLOR}[!]${RESET_COLOR} $1"; }
err() { echo -e "${ERR_COLOR}[x]${RESET_COLOR} $1"; }

require_command() {
  if ! command -v "$1" >/dev/null 2>&1; then
    err "Missing required command: $1" && exit 1
  fi
}

port_in_use() {
  local port="$1"
  if command -v ss >/dev/null 2>&1; then
    ss -ltn | awk '{print $4}' | grep -Eq "(^|:)${port}$"
  else
    netstat -ltn 2>/dev/null | awk '{print $4}' | grep -Eq "(^|:)${port}$"
  fi
}

suggest_free_port() {
  local candidates=($@)
  for p in "${candidates[@]}"; do
    if ! port_in_use "$p"; then
      echo "$p"
      return 0
    fi
  done
  echo ""
}

prompt_with_default() {
  local prompt="$1"
  local default_value="$2"
  local secret="${3:-false}"
  local value
  if [ "$secret" = "true" ]; then
    read -r -s -p "$prompt [$default_value]: " value
    echo
  else
    read -r -p "$prompt [$default_value]: " value
  fi
  echo "${value:-$default_value}"
}

install_packages() {
  if command -v apt-get >/dev/null 2>&1; then
    log "Updating apt cache and installing dependencies..."
    sudo apt-get update -y
    sudo apt-get install -y git python3 python3-venv python3-pip nodejs npm ffmpeg
  elif command -v dnf >/dev/null 2>&1; then
    log "Updating dnf and installing dependencies..."
    sudo dnf install -y git python3 python3-venv python3-pip nodejs npm ffmpeg
  elif command -v yum >/dev/null 2>&1; then
    log "Updating yum and installing dependencies..."
    sudo yum install -y git python3 python3-venv python3-pip nodejs npm ffmpeg
  else
    err "Unsupported package manager. Install git, Python 3, and Node.js manually." && exit 1
  fi
}

start_backend() {
  local workdir="$1"
  local port="$2"
  log "Starting backend on port $port..."
  (cd "$workdir" && \
    set -a && source backend/.env && set +a && \
    source .venv/bin/activate && \
    nohup uvicorn backend.app.main:app --host 0.0.0.0 --port "$port" > "$workdir/backend.log" 2>&1 & echo $! > "$workdir/backend.pid")
  log "Backend log: $workdir/backend.log"
}

start_frontend() {
  local workdir="$1"
  local port="$2"
  log "Starting frontend (Vite preview) on port $port..."
  (cd "$workdir/frontend" && \
    nohup npm run preview -- --host --port "$port" > "$workdir/frontend.log" 2>&1 & echo $! > "$workdir/frontend.pid")
  log "Frontend log: $workdir/frontend.log"
}

stop_if_running() {
  local pid_file="$1"
  if [ -f "$pid_file" ]; then
    local pid
    pid=$(cat "$pid_file" 2>/dev/null || true)
    if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
      warn "Stopping existing process with PID $pid (from $pid_file)"
      kill "$pid" || true
    fi
    rm -f "$pid_file"
  fi
}

main() {
  install_packages

  local default_repo="https://github.com/your-org/ventout.git"
  local repo_url
  repo_url=$(prompt_with_default "Git repository to clone" "$default_repo")
  local branch
  branch=$(prompt_with_default "Branch or tag" "main")
  local install_dir
  install_dir=$(prompt_with_default "Install directory" "$HOME/listener-ai")

  mkdir -p "$install_dir"
  cd "$install_dir"

  if [ ! -d "ventout/.git" ]; then
    log "Cloning $repo_url (branch $branch) into $install_dir/ventout..."
    git clone --branch "$branch" "$repo_url" ventout
  else
    log "Existing repository found; pulling latest..."
    (cd ventout && git pull)
  fi

  cd ventout

  # Ports: prefer security-group-open ports 80, 443, 3000, 8000 if free.
  local backend_default
  backend_default=$(suggest_free_port 8000 3000 8081 8080 9000)
  backend_default=${backend_default:-8000}
  local backend_port
  backend_port=$(prompt_with_default "Backend port (open SG ports: 80, 443, 3000, 8000)" "$backend_default")
  while port_in_use "$backend_port"; do
    backend_port=$(prompt_with_default "Port $backend_port is busy. Pick another backend port" "$backend_default")
  done

  local frontend_default
  frontend_default=$(suggest_free_port 3000 4173 5173 8082 7000)
  frontend_default=${frontend_default:-4173}
  local frontend_port
  frontend_port=$(prompt_with_default "Frontend port (open SG ports: 80, 443, 3000, 8000)" "$frontend_default")
  while [ "$frontend_port" = "$backend_port" ] || port_in_use "$frontend_port"; do
    frontend_port=$(prompt_with_default "Port $frontend_port is busy or clashes with backend. Pick another frontend port" "$frontend_default")
  done

  warn "Ensure your EC2 security group allows inbound access to the chosen ports."

  # Secrets & env
  local openai_key
  openai_key=$(prompt_with_default "OpenAI API key" "" true)
  local jwt_secret
  jwt_secret=$(prompt_with_default "JWT secret" "change-me" true)
  local postgres_url
  postgres_url=$(prompt_with_default "Postgres URL (leave blank for dev sqlite)" "")

  local use_s3
  use_s3=$(prompt_with_default "Enable S3 uploads for raw audio? (y/n)" "n")
  local s3_bucket=""
  local s3_region="us-east-1"
  local s3_prefix="voice-notes"
  if [[ "$use_s3" =~ ^[Yy]$ ]]; then
    s3_bucket=$(prompt_with_default "S3 bucket name" "listener-audio")
    s3_region=$(prompt_with_default "S3 region" "$s3_region")
    s3_prefix=$(prompt_with_default "S3 prefix" "$s3_prefix")
  fi

  cat > backend/.env <<EOF_ENV
OPENAI_API_KEY=${openai_key}
OPENAI_TRANSCRIBE_MODEL=gpt-4o-mini-transcribe
OPENAI_TTS_MODEL=gpt-4o-mini-tts
OPENAI_TTS_VOICE=alloy
OPENAI_TTS_STYLE=calm
OPENAI_SAFETY_MODEL=gpt-4o-mini
OPENAI_REALTIME_MODEL=gpt-4o-realtime-preview
JWT_SECRET=${jwt_secret}
POSTGRES_URL=${postgres_url}
S3_BUCKET=${s3_bucket}
S3_REGION=${s3_region}
S3_PREFIX=${s3_prefix}
COOLDOWN_SECONDS=60
BACKEND_PORT=${backend_port}
FRONTEND_PORT=${frontend_port}
EOF_ENV

  log "Installing backend dependencies..."
  python3 -m venv .venv
  source .venv/bin/activate
  pip install --upgrade pip
  pip install -r backend/requirements.txt
  deactivate

  log "Installing frontend dependencies..."
  (cd frontend && npm install && npm run build)

  stop_if_running "$(pwd)/backend.pid"
  stop_if_running "$(pwd)/frontend.pid"

  start_backend "$(pwd)" "$backend_port"
  start_frontend "$(pwd)" "$frontend_port"

  log "Done. Export env for shells with:"
  echo "  set -a; source $(pwd)/backend/.env; set +a"
  log "Backend available on port $backend_port. Frontend available on port $frontend_port."
  warn "If the chosen ports are not open in your security group, update the rules or use an allowed port."
}

main "$@"
