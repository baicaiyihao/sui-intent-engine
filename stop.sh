#!/usr/bin/env bash
# stop.sh — shut down the SUI Intent Engine stack started by start.sh
#
# Reads PIDs from .pids/, sends SIGTERM, falls back to SIGKILL after 3s.
# Frees ports 3000 / 8000 / 8001.

set -e
# zsh: don't error on missing globs; bash: no equivalent needed
[ -n "$ZSH_VERSION" ] && setopt NULL_GLOB 2>/dev/null || true

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

if [ -t 1 ]; then
  C_GREEN='\033[0;32m'
  C_YELLOW='\033[0;33m'
  C_RED='\033[0;31m'
  C_RESET='\033[0m'
else
  C_GREEN=''; C_YELLOW=''; C_RED=''; C_RESET=''
fi
say()  { printf "${C_GREEN}[stop]${C_RESET} %s\n" "$*"; }
warn() { printf "${C_YELLOW}[stop]${C_RESET} %s\n" "$*" >&2; }
fail() { printf "${C_RED}[stop]${C_RESET} %s\n" "$*" >&2; exit 1; }

stop_pid() {
  local name=$1 pidfile=$2
  if [ ! -f "$pidfile" ]; then
    return
  fi
  local pid
  pid=$(cat "$pidfile" 2>/dev/null || echo "")
  if [ -z "$pid" ] || ! kill -0 "$pid" 2>/dev/null; then
    rm -f "$pidfile"
    return
  fi
  say "stopping $name (pid=$pid)"
  kill "$pid" 2>/dev/null || true
  for _ in 1 2 3 4 5 6; do
    if ! kill -0 "$pid" 2>/dev/null; then break; fi
    sleep 0.5
  done
  if kill -0 "$pid" 2>/dev/null; then
    warn "$name (pid=$pid) did not exit in 3s — SIGKILL"
    kill -9 "$pid" 2>/dev/null || true
  fi
  rm -f "$pidfile"
}

stop_port() {
  local name=$1 port=$2
  local pid
  pid=$(lsof -ti:"$port" -sTCP:LISTEN 2>/dev/null || true)
  if [ -n "$pid" ]; then
    warn "$name :$port still has listener pid=$pid — killing"
    kill -9 "$pid" 2>/dev/null || true
  fi
}

stop_pid "frontend"       "$ROOT/.pids/3000.pid"
stop_pid "backend-A"      "$ROOT/.pids/8000.pid"
stop_pid "backend-B"      "$ROOT/.pids/8001.pid"

# Safety net: anything still listening on our ports?
stop_port "frontend"  3000
stop_port "backend-A" 8000
stop_port "backend-B" 8001

say "done"
