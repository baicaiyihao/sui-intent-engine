#!/usr/bin/env bash
# start.sh — boot the full SUI Intent Engine stack
#
# Auto-installs deps on first run, detects Python env (conda 'crawl4ai' or
# .venv fallback), and starts 3 services in the background:
#   - Backend A  (QuantCore AI)        :8000
#   - Backend B  (SuiIntent Engine)    :8001
#   - Frontend   (Vite + React)        :3000
#
# PIDs  -> .pids/
# Logs  -> logs/
# Use ./stop.sh to shut everything down.

set -e

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

mkdir -p .pids logs

# ---------- colors ----------
if [ -t 1 ]; then
  C_GREEN='\033[0;32m'
  C_YELLOW='\033[0;33m'
  C_RED='\033[0;31m'
  C_DIM='\033[2m'
  C_RESET='\033[0m'
else
  C_GREEN=''; C_YELLOW=''; C_RED=''; C_DIM=''; C_RESET=''
fi
say()   { printf "${C_GREEN}[start]${C_RESET} %s\n" "$*"; }
warn()  { printf "${C_YELLOW}[start]${C_RESET} %s\n" "$*" >&2; }
fail()  { printf "${C_RED}[start]${C_RESET} %s\n" "$*" >&2; exit 1; }
note()  { printf "${C_DIM}[start]${C_RESET} %s\n" "$*"; }

# ---------- port helpers ----------
is_listening() {
  lsof -ti:"$1" -sTCP:LISTEN >/dev/null 2>&1
}
port_owner() {
  lsof -ti:"$1" -sTCP:LISTEN 2>/dev/null | head -1
}

# ---------- detect Python env ----------
detect_python() {
  # Look for the real conda binary in common install locations
  # (the `conda` shell function from ~/.zshrc is NOT visible in a non-interactive
  # script — we need the actual executable)
  local conda_bin=""
  for candidate in \
    "$HOME/miniconda3/bin/conda" \
    "$HOME/anaconda3/bin/conda" \
    "$HOME/miniforge3/bin/conda" \
    "$HOME/mambaforge/bin/conda" \
    "/opt/homebrew/bin/conda" \
    "/usr/local/bin/conda" \
    "/opt/conda/bin/conda"; do
    if [ -x "$candidate" ]; then
      conda_bin="$candidate"
      break
    fi
  done

  if [ -n "$conda_bin" ] && "$conda_bin" env list 2>/dev/null | grep -qE 'crawl4ai'; then
    PYTHON_CMD=("$conda_bin" run -n crawl4ai --no-capture-output python)
    PY_LABEL="conda:crawl4ai"
  elif [ -x "$ROOT/.venv/bin/python" ]; then
    PYTHON_CMD=("$ROOT/.venv/bin/python")
    PY_LABEL=".venv"
  elif command -v python3 >/dev/null 2>&1; then
    note "no conda 'crawl4ai' env, no .venv — creating .venv"
    python3 -m venv "$ROOT/.venv"
    "$ROOT/.venv/bin/pip" install --upgrade pip -q
    "$ROOT/.venv/bin/pip" install -r "$ROOT/requirements.txt" -q
    PYTHON_CMD=("$ROOT/.venv/bin/python")
    PY_LABEL=".venv (newly created)"
  else
    fail "no python3 found and no conda 'crawl4ai' env — install Python 3.10+ or set up conda"
  fi
}

# ---------- detect Node ----------
detect_node() {
  if ! command -v node >/dev/null 2>&1; then
    fail "node not found — install Node 18+ from https://nodejs.org"
  fi
  if ! command -v npm >/dev/null 2>&1; then
    fail "npm not found — install Node 18+ (npm ships with node)"
  fi
  NODE_V=$(node --version | sed 's/^v//')
  NODE_MAJOR=$(echo "$NODE_V" | cut -d. -f1)
  if [ "$NODE_MAJOR" -lt 18 ] 2>/dev/null; then
    warn "node $NODE_V detected — 18+ recommended (Vite 5 requires it)"
  fi
}

# ---------- preflight: bail if ports busy with foreign pids ----------
preflight_ports() {
  local busy=0
  for p in 3000 8000 8001; do
    if is_listening "$p"; then
      local pid
      pid=$(port_owner "$p")
      if [ -f "$ROOT/.pids/$p.pid" ] && [ "$pid" = "$(cat "$ROOT/.pids/$p.pid" 2>/dev/null)" ]; then
        note "port $p already serving from our pid $pid — leaving it"
      else
        warn "port $p in use by foreign pid $pid — run ./stop.sh first, or:  kill $pid"
        busy=1
      fi
    fi
  done
  [ "$busy" -eq 0 ] || fail "aborting — clean up foreign processes first"
}

# ---------- install Python deps if missing ----------
ensure_python_deps() {
  if "${PYTHON_CMD[@]}" -c "import fastapi, uvicorn, pandas, numpy, aiohttp, ccxt, requests" 2>/dev/null; then
    note "python deps already installed ($PY_LABEL)"
    return
  fi
  say "installing python deps into $PY_LABEL (one-time, ~30s)..."
  if [ "$PY_LABEL" = "conda:crawl4ai" ]; then
    fail "deps missing in conda:crawl4ai — run:  conda run -n crawl4ai pip install -r requirements.txt"
  fi
  "${PYTHON_CMD[@]}" -m pip install -r "$ROOT/requirements.txt" -q
  say "python deps installed"
}

# ---------- install Node deps if missing ----------
ensure_node_deps() {
  if [ -d "$ROOT/src/frontend/node_modules" ] && [ -f "$ROOT/src/frontend/node_modules/.package-lock.json" ]; then
    note "node deps already installed (src/frontend/node_modules)"
    return
  fi
  say "installing node deps (one-time, ~60s)..."
  (cd "$ROOT/src/frontend" && npm install --no-audit --no-fund)
  say "node deps installed"
}

# ---------- start a single service ----------
start_service() {
  local max_wait=$1 name=$2 port=$3 logfile=$4 pidfile=$5
  shift 5
  if is_listening "$port"; then
    local existing
    existing=$(port_owner "$port")
    echo "$existing" > "$ROOT/$pidfile"
    note "$name :$port already running (pid=$existing)"
    return
  fi
  say "starting $name on :$port (log: $logfile, max_wait=${max_wait}s)"
  nohup "$@" >"$ROOT/$logfile" 2>&1 &
  local wrapper_pid=$!
  disown "$wrapper_pid" 2>/dev/null || true
  # Backends do heavy lifespan init (DB, deepbook indexer sync via sync I/O in
  # the event loop, LLM client). Then read the REAL pid from the port listener,
  # since `$!` is the nohup wrapper and may differ from the actual python
  # process on BSD nohup.
  local real_pid=""
  for i in $(seq 1 "$max_wait"); do
    if is_listening "$port"; then
      real_pid=$(port_owner "$port")
      break
    fi
    if ! kill -0 "$wrapper_pid" 2>/dev/null; then
      fail "$name :$port process died — check $logfile"
    fi
    sleep 1
  done
  if [ -n "$real_pid" ]; then
    echo "$real_pid" > "$ROOT/$pidfile"
    say "$name :$port up (pid=$real_pid, after ${i}s)"
  else
    warn "$name :$port did not bind in ${max_wait}s — check $logfile"
    echo "$wrapper_pid" > "$ROOT/$pidfile"
  fi
}

# ============================================================================
# main
# ============================================================================
say "SUI Intent Engine — full stack"
note "root: $ROOT"

preflight_ports
detect_python
detect_node
ensure_python_deps
ensure_node_deps

# Backend A — QuantCore AI (port 8000)
start_service 15 "backend-A (QuantCore AI)" 8000 \
  logs/backend-A.log .pids/8000.pid \
  "${PYTHON_CMD[@]}" -m uvicorn src.server:app --host 0.0.0.0 --port 8000

# Backend B — SuiIntent (port 8001) — mainnet deepbook indexer can be slow on cold start
start_service 60 "backend-B (SuiIntent)" 8001 \
  logs/backend-B.log .pids/8001.pid \
  "${PYTHON_CMD[@]}" -m uvicorn src.sui_intent_server:app --host 0.0.0.0 --port 8001

# Frontend — Vite (port 3000)
start_service 15 "frontend (Vite + React)" 3000 \
  logs/frontend.log .pids/3000.pid \
  npm --prefix "$ROOT/src/frontend" run dev -- --host 0.0.0.0

echo
say "stack is up"
printf "  ${C_GREEN}Frontend${C_RESET}    → ${C_GREEN}http://localhost:3000${C_RESET}\n"
printf "  ${C_GREEN}Backend A${C_RESET}   → ${C_GREEN}http://localhost:8000${C_RESET}  (QuantCore AI, /docs for Swagger)\n"
printf "  ${C_GREEN}Backend B${C_RESET}   → ${C_GREEN}http://localhost:8001${C_RESET}  (SuiIntent,   /docs for Swagger)\n"
echo
printf "${C_DIM}logs:   logs/{backend-A,backend-B,frontend}.log${C_RESET}\n"
printf "${C_DIM}stop:   ./stop.sh${C_RESET}\n"
