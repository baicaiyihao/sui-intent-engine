#!/usr/bin/env bash
# deploy.sh — one-shot backend deploy for SUI Intent Engine on Ubuntu 22.04
#
# Pre-requisites (you've already done these):
#   - nginx installed and a site enabled for api.your.duckdns.org
#   - certbot --nginx -d api.your.duckdns.org completed
#   - duckdns.org subdomain created and pointing at this VPS IP
#   - 80/443 open in cloud firewall + UFW
#
# What this script does:
#   1. Installs Python deps (system pip or creates .venv)
#   2. Writes systemd services for backend-A (:8000) and backend-B (:8001)
#   3. Sets up duckdns auto-update cron (every 5 min)
#   4. Starts services, waits, runs health checks
#   5. Prints a summary with the public URL
#
# Idempotent — safe to re-run.
set -e

# ---------- config ----------
APP_DIR="${APP_DIR:-/root/sui-intent-engine}"
DUCKDNS_DOMAIN="${DUCKDNS_DOMAIN:-sui-intent}"
DUCKDNS_TOKEN="${DUCKDNS_TOKEN:-YOUR_DUCKDNS_TOKEN_HERE}"
GIT_REPO="${GIT_REPO:-https://github.com/baicaiyihao/sui-intent-engine.git}"
GIT_BRANCH="${GIT_BRANCH:-main}"
PYTHON_BIN="${PYTHON_BIN:-python3}"
USE_VENV="${USE_VENV:-1}"   # set USE_VENV=0 to use system pip

# ---------- colors ----------
if [ -t 1 ]; then
  C_GREEN='\033[0;32m'; C_YELLOW='\033[0;33m'; C_RED='\033[0;31m'; C_DIM='\033[2m'; C_RESET='\033[0m'
else
  C_GREEN=''; C_YELLOW=''; C_RED=''; C_DIM=''; C_RESET=''
fi
say()  { printf "${C_GREEN}[deploy]${C_RESET} %s\n" "$*"; }
warn() { printf "${C_YELLOW}[deploy]${C_RESET} %s\n" "$*" >&2; }
fail() { printf "${C_RED}[deploy]${C_RESET} %s\n" "$*" >&2; exit 1; }

# ---------- preflight ----------
[ "$(id -u)" -eq 0 ] || fail "Run as root (sudo $0)"
say "Deploying SUI Intent Engine backend"
say "  APP_DIR=$APP_DIR"
say "  DUCKDNS=$DUCKDNS_DOMAIN.duckdns.org"
say "  GIT_REPO=$GIT_REPO@$GIT_BRANCH"
say ""

# ---------- 1. system deps ----------
say "1. Installing system deps (python3-pip + git)..."
apt update -y
apt install -y python3-pip python3-venv git curl lsof >/dev/null

# ---------- 2. clone / update repo ----------
if [ -d "$APP_DIR/.git" ]; then
  say "2. Repo exists, pulling latest..."
  cd "$APP_DIR"
  git fetch origin "$GIT_BRANCH"
  git reset --hard "origin/$GIT_BRANCH"
else
  say "2. Cloning repo to $APP_DIR..."
  git clone --branch "$GIT_BRANCH" "$GIT_REPO" "$APP_DIR"
  cd "$APP_DIR"
fi

# ---------- 3. quant_core sibling ----------
QUANT_CORE_DIR="$(dirname "$APP_DIR")/quant_core"
if [ ! -d "$QUANT_CORE_DIR/.git" ]; then
  say "3. Cloning quant_core sibling..."
  git clone https://github.com/baicaiyihao/quant_core.git "$QUANT_CORE_DIR" || \
    warn "quant_core clone failed — backend-A may not work. See requirements.txt header."
else
  say "3. quant_core sibling already at $QUANT_CORE_DIR"
fi
export PYTHONPATH="$QUANT_CORE_DIR:$APP_DIR/src"

# ---------- 4. python env ----------
if [ "$USE_VENV" = "1" ]; then
  if [ ! -d "$APP_DIR/.venv" ]; then
    say "4. Creating .venv..."
    $PYTHON_BIN -m venv "$APP_DIR/.venv"
  fi
  PIP="$APP_DIR/.venv/bin/pip"
  PY="$APP_DIR/.venv/bin/python"
  say "4. Installing Python deps (this takes 2-3 min)..."
  "$PIP" install -U pip wheel setuptools >/dev/null
  "$PIP" install -r "$APP_DIR/requirements.txt" >/dev/null
else
  PIP="pip3"
  PY="python3"
  say "4. Installing Python deps (system pip)..."
  pip3 install -U pip >/dev/null
  pip3 install -r "$APP_DIR/requirements.txt" >/dev/null
fi

# ---------- 5. .env ----------
if [ ! -f "$APP_DIR/src/.env" ]; then
  warn "5. $APP_DIR/src/.env missing — copying template"
  cp "$APP_DIR/src/.env.example" "$APP_DIR/src/.env"
  warn "   ⚠️  Edit $APP_DIR/src/.env and fill in MINIMAX_API_KEY (and any other keys)"
  warn "   Then re-run this script. Backend-A will start without keys but AI features will be disabled."
fi

# ---------- 6. systemd services ----------
write_service() {
  local name="$1" exec_cmd="$2" port="$3"
  local svc="/etc/systemd/system/sui-intent-$name.service"
  cat > "$svc" <<EOF
[Unit]
Description=SUI Intent Engine - $name (:$port)
After=network.target

[Service]
Type=simple
WorkingDirectory=$APP_DIR
Environment="PATH=$APP_DIR/.venv/bin:/usr/local/bin:/usr/bin:/bin"
Environment="PYTHONPATH=$QUANT_CORE_DIR:$APP_DIR/src"
ExecStart=$exec_cmd
Restart=always
RestartSec=3
User=root
StandardOutput=append:/var/log/sui-intent-$name.log
StandardError=append:/var/log/sui-intent-$name.log

[Install]
WantedBy=multi-user.target
EOF
  systemctl daemon-reload
  systemctl enable --now "sui-intent-$name.service"
  say "   ✓ $name :$port  (PID: $(systemctl show -p MainPID --value "sui-intent-$name.service"))"
}

if [ "$USE_VENV" = "1" ]; then
  EXEC_A="$APP_DIR/.venv/bin/uvicorn src.server:app --host 127.0.0.1 --port 8000"
  EXEC_B="$APP_DIR/.venv/bin/uvicorn src.sui_intent_server:app --host 127.0.0.1 --port 8001"
else
  EXEC_A="uvicorn src.server:app --host 127.0.0.1 --port 8000"
  EXEC_B="uvicorn src.sui_intent_server:app --host 127.0.0.1 --port 8001"
fi

say "6. Writing systemd services..."
# kill any existing uvicorn first (in case the user ran nohup before)
pkill -f 'uvicorn src.server:app'         2>/dev/null || true
pkill -f 'uvicorn src.sui_intent_server'  2>/dev/null || true
sleep 1
write_service "backend-A" "$EXEC_A" 8000
write_service "backend-B" "$EXEC_B" 8001

# ---------- 7. duckdns auto-update cron ----------
say "7. Installing duckdns auto-update cron (every 5 min)..."
if [ "$DUCKDNS_TOKEN" = "YOUR_DUCKDNS_TOKEN_HERE" ]; then
  warn "   DUCKDNS_TOKEN is the default placeholder — skipping cron install."
  warn "   Get your token from https://www.duckdns.org/ (top-right 'token' field)"
  warn "   Then re-run:  DUCKDNS_TOKEN=xxx $0"
else
  CRON_CMD="*/5 * * * * curl -fsS 'https://www.duckdns.org/update?domains=$DUCKDNS_DOMAIN&token=$DUCKDNS_TOKEN&ip=' >/dev/null 2>&1"
  ( crontab -l 2>/dev/null | grep -v 'duckdns.org/update' ; echo "$CRON_CMD" ) | crontab -
  say "   ✓ cron installed"
  # also update now so the IP is current
  curl -fsS "https://www.duckdns.org/update?domains=$DUCKDNS_DOMAIN&token=$DUCKDNS_TOKEN&ip="
fi

# ---------- 8. UFW ----------
say "8. Configuring UFW (22/80/443)..."
ufw allow 22/tcp  >/dev/null
ufw allow 80/tcp  >/dev/null
ufw allow 443/tcp >/dev/null
ufw --force enable >/dev/null
say "   ✓ UFW: $(ufw status | head -1)"

# ---------- 9. health check ----------
say "9. Health check (waiting 8s for backends to boot)..."
sleep 8
ok_a=$(curl -sf -o /dev/null -w "%{http_code}" http://127.0.0.1:8000/api/v1/market/ticker 2>/dev/null || echo "FAIL")
ok_b=$(curl -sf -o /dev/null -w "%{http_code}" http://127.0.0.1:8001/api/v1/cache/ticker  2>/dev/null || echo "FAIL")
case "$ok_a" in 2*|3*) say "   ✓ backend-A :8000  → HTTP $ok_a" ;; *) fail "   ✗ backend-A :8000  → HTTP $ok_a  (see /var/log/sui-intent-backend-A.log)" ;; esac
case "$ok_b" in 2*|3*) say "   ✓ backend-B :8001  → HTTP $ok_b" ;; *) fail "   ✗ backend-B :8001  → HTTP $ok_b  (see /var/log/sui-intent-backend-B.log)" ;; esac

# ---------- summary ----------
cat <<EOF

${C_GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${C_RESET}
${C_GREEN}  SUI Intent Engine backend deployed${C_RESET}
${C_GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${C_RESET}

  Backend A  http://127.0.0.1:8000   (127.0.0.1 only — nginx fronts it)
  Backend B  http://127.0.0.1:8001   (127.0.0.1 only — nginx fronts it)

  Public URL:  https://$DUCKDNS_DOMAIN.duckdns.org
    /api/*    → :8000
    /intent/* → :8001
    /market/* → :8001

  ${C_DIM}Useful commands:${C_RESET}
    systemctl status sui-intent-backend-A
    systemctl status sui-intent-backend-B
    journalctl -u sui-intent-backend-A -f
    tail -f /var/log/sui-intent-backend-A.log

  ${C_DIM}Next step (Vercel frontend):${C_RESET}
    Add vercel.json with rewrites to https://$DUCKDNS_DOMAIN.duckdns.org
    See DEPLOY.md for the exact config.

EOF
