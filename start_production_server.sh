#!/usr/bin/env bash
# =============================================================================
# start_server.sh — Clean restart for gunicorn (Django / WSGI)
# Usage:
#   ./start_server.sh            # defaults to staging
#   ./start_server.sh production # production mode
#
# Serves the app directly on $PORT with no reverse proxy: gunicorn handles
# dynamic requests, WhiteNoise handles /static, and Django serves /media off
# the instance's own disk (see config/urls.py).
# =============================================================================

set -euo pipefail

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
ENV="${1:-staging}"
APP_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV_DIR="$APP_DIR/venv"
PORT=5000
WSGI_MODULE="config.wsgi:application"
LOG_DIR="$APP_DIR/logs"

# PID file — lets us kill precisely without lsof
GUNICORN_PID="$APP_DIR/gunicorn.pid"

# Journald identifier (used when USE_JOURNALD=true)
GUNICORN_TAG="agency-gunicorn"

# Use journald if systemd-cat is available, otherwise fall back to log files
USE_JOURNALD=false
command -v systemd-cat &>/dev/null && USE_JOURNALD=true

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
info()  { echo -e "\033[0;34m[INFO]\033[0m  $*"; }
ok()    { echo -e "\033[0;32m[ OK ]\033[0m  $*"; }
warn()  { echo -e "\033[0;33m[WARN]\033[0m  $*"; }
die()   { echo -e "\033[0;31m[ERR ]\033[0m  $*" >&2; exit 1; }

kill_pid_file() {
  local pidfile="$1" label="$2"
  if [[ -f "$pidfile" ]]; then
    local pid
    pid=$(cat "$pidfile")
    if kill -0 "$pid" 2>/dev/null; then
      info "Stopping $label (PID $pid)…"
      kill "$pid" 2>/dev/null || true
      # Wait out the graceful shutdown rather than assuming one second is enough.
      local waited=0
      while kill -0 "$pid" 2>/dev/null && (( waited < 15 )); do
        sleep 1
        (( waited++ )) || true
      done
      if kill -0 "$pid" 2>/dev/null; then
        kill -9 "$pid" 2>/dev/null || true
        warn "Force-killed $label after ${waited}s"
      else
        ok "$label stopped cleanly"
      fi
    else
      warn "$label PID file exists but process already gone — cleaning up"
    fi
    rm -f "$pidfile"
  fi
}

kill_port() {
  local port="$1"
  local pids
  if ! command -v lsof &>/dev/null; then
    warn "lsof not installed — cannot verify port $port is free"
    return 0
  fi
  pids=$(lsof -ti :"$port" 2>/dev/null || true)
  if [[ -n "$pids" ]]; then
    info "Releasing port $port (PIDs: $pids)…"
    echo "$pids" | xargs kill -9 2>/dev/null || true
    sleep 1
  fi
}

# ---------------------------------------------------------------------------
# 1. Validate environment
# ---------------------------------------------------------------------------
[[ "$ENV" == "staging" || "$ENV" == "production" ]] \
  || die "Unknown environment '$ENV'. Use 'staging' or 'production'."

info "Environment : $ENV"
info "App dir     : $APP_DIR"
info "Port        : $PORT"
info "Journald    : $USE_JOURNALD"
[[ -d "$APP_DIR" ]] || die "App directory not found: $APP_DIR"

cd "$APP_DIR"

# Neither environment is a developer laptop, so never inherit DEBUG=True from
# .env. python-dotenv does not overwrite variables that are already exported,
# so setting it here wins over the .env file.
export DEBUG=False

# ---------------------------------------------------------------------------
# 2. Activate virtualenv
# ---------------------------------------------------------------------------
[[ -f "$VENV_DIR/bin/activate" ]] || die "Virtualenv not found at $VENV_DIR"
# shellcheck source=/dev/null
source "$VENV_DIR/bin/activate"
ok "Virtualenv activated: $VENV_DIR"

# ---------------------------------------------------------------------------
# 3. Pre-flight checks — fail before touching the running server
# ---------------------------------------------------------------------------
info "=== Pre-flight checks ==="
python manage.py check --deploy --fail-level ERROR \
  || die "Django deployment check failed — aborting (old server left running)."

# ALLOWED_HOSTS defaults to empty, and every request 400s without it.
python - <<'PY' || die "ALLOWED_HOSTS is empty — set it in .env or the environment."
import os, sys, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()
from django.conf import settings
sys.exit(0 if settings.ALLOWED_HOSTS else 1)
PY
ok "Configuration valid for DEBUG=False"

# ---------------------------------------------------------------------------
# 4. Stop existing processes (clean slate)
# ---------------------------------------------------------------------------
info "=== Stopping existing processes ==="
kill_pid_file "$GUNICORN_PID" "Gunicorn"

# Belt-and-suspenders: also free the port in case PID file was missing
kill_port "$PORT"

# ---------------------------------------------------------------------------
# 5. Prepare directories
# ---------------------------------------------------------------------------
mkdir -p "$LOG_DIR"
# media/ is gitignored, so a fresh instance has no such directory. Django
# creates it on first upload, but /media/ 404s until then.
mkdir -p "$APP_DIR/media"

# ---------------------------------------------------------------------------
# 6. Django migrations
# ---------------------------------------------------------------------------
info "=== Running Django migrations ==="
if ! migration_out=$(python manage.py migrate --noinput 2>&1); then
  echo "$migration_out"
  die "Django migration failed — aborting server start."
fi
echo "$migration_out"
ok "Database migrations up to date"

# ---------------------------------------------------------------------------
# 7. Collect static files
# ---------------------------------------------------------------------------
# No --clear: wiping STATIC_ROOT first leaves a window where every asset 404s,
# and collectstatic overwrites changed files anyway.
info "=== Collecting static files ==="
python manage.py collectstatic --noinput 2>&1 | tail -5
ok "Static files collected"

# ---------------------------------------------------------------------------
# 8. Gunicorn flags per environment
# ---------------------------------------------------------------------------
if [[ "$ENV" == "production" ]]; then
  WORKERS=4
else
  WORKERS=2
fi

GUNICORN_ARGS=(
  "$WSGI_MODULE"
  --bind "0.0.0.0:$PORT"
  --workers "$WORKERS"
  --pid "$GUNICORN_PID"
  --timeout 60
  --graceful-timeout 30
  # Recycle workers periodically so a slow leak can never accumulate; the
  # jitter stops every worker restarting on the same request count.
  --max-requests 1000
  --max-requests-jitter 100
)

# ---------------------------------------------------------------------------
# 9. Launch Gunicorn
# ---------------------------------------------------------------------------
info "=== Starting Gunicorn ($ENV, $WORKERS workers) ==="

if $USE_JOURNALD; then
  # Drop --daemon so journald captures stdout. --pid makes gunicorn write its
  # own master PID: recording $! here would capture the wrapper shell instead,
  # and killing that leaves gunicorn alive and still holding the port.
  rm -f "$GUNICORN_PID"
  nohup bash -c "
    $VENV_DIR/bin/gunicorn ${GUNICORN_ARGS[*]} \
      --access-logfile - \
      --error-logfile - 2>&1 \
    | systemd-cat -t $GUNICORN_TAG -p info
  " >/dev/null 2>&1 &
else
  gunicorn "${GUNICORN_ARGS[@]}" \
    --access-logfile "$LOG_DIR/access.log" \
    --error-logfile  "$LOG_DIR/error.log" \
    --capture-output \
    --daemon
fi

# ---------------------------------------------------------------------------
# 10. Health check — confirm the app actually serves, not just that a PID exists
# ---------------------------------------------------------------------------
info "=== Waiting for the app to respond on port $PORT ==="
HEALTH_OK=false
code=""
for _ in $(seq 1 20); do
  code=$(curl -s -o /dev/null -w '%{http_code}' --max-time 2 "http://127.0.0.1:$PORT/" || true)
  if [[ "$code" =~ ^[23] ]]; then
    HEALTH_OK=true
    break
  fi
  sleep 1
done

echo ""
info "=== Process summary ==="
if $HEALTH_OK; then
  ok "Gunicorn is serving HTTP $code on port $PORT (PID $(cat "$GUNICORN_PID" 2>/dev/null || echo '?'))"
else
  warn "App did NOT return a healthy response (last status: ${code:-none}) — check logs"
fi

echo ""
if $USE_JOURNALD; then
  info "=== Tail logs with journalctl ==="
  echo "  journalctl -t $GUNICORN_TAG -f"
else
  info "=== Tail log files ==="
  echo "  tail -f $LOG_DIR/access.log"
  echo "  tail -f $LOG_DIR/error.log"
fi

echo ""
if $HEALTH_OK; then
  ok "Server started in $ENV mode — http://0.0.0.0:$PORT"
else
  die "Server start could not be confirmed."
fi
