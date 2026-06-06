#!/usr/bin/env bash
# =============================================================================
# start_server.sh — Clean restart for gunicorn (Django / WSGI)
# Usage:
#   ./start_server.sh            # defaults to staging
#   ./start_server.sh production # production mode
# =============================================================================

set -euo pipefail

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
ENV="${1:-staging}"
APP_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV_DIR="$APP_DIR/venv"
PORT=8005
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
      kill "$pid" && sleep 1
      kill -0 "$pid" 2>/dev/null && kill -9 "$pid" && warn "Force-killed $label"
    else
      warn "$label PID file exists but process already gone — cleaning up"
    fi
    rm -f "$pidfile"
  fi
}

kill_port() {
  local port="$1"
  local pids
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

# ---------------------------------------------------------------------------
# 2. Activate virtualenv
# ---------------------------------------------------------------------------
[[ -f "$VENV_DIR/bin/activate" ]] || die "Virtualenv not found at $VENV_DIR"
# shellcheck source=/dev/null
source "$VENV_DIR/bin/activate"
ok "Virtualenv activated: $VENV_DIR"

# ---------------------------------------------------------------------------
# 3. Stop existing processes (clean slate)
# ---------------------------------------------------------------------------
info "=== Stopping existing processes ==="
kill_pid_file "$GUNICORN_PID" "Gunicorn"

# Belt-and-suspenders: also free the port in case PID file was missing
kill_port "$PORT"

sleep 1

# ---------------------------------------------------------------------------
# 4. Prepare logs
# ---------------------------------------------------------------------------
mkdir -p "$LOG_DIR"

# ---------------------------------------------------------------------------
# 5. Django migrations
# ---------------------------------------------------------------------------
info "=== Running Django migrations ==="
if ! migration_out=$(python manage.py migrate --noinput 2>&1); then
  echo "$migration_out"
  die "Django migration failed — aborting server start."
fi
echo "$migration_out"
ok "Database migrations up to date"

# ---------------------------------------------------------------------------
# 6. Collect static files
# ---------------------------------------------------------------------------
info "=== Collecting static files ==="
python manage.py collectstatic --noinput --clear 2>&1 | tail -5
ok "Static files collected"

# ---------------------------------------------------------------------------
# 7. Gunicorn flags per environment
# ---------------------------------------------------------------------------
if [[ "$ENV" == "production" ]]; then
  WORKERS=4
else
  WORKERS=2
fi

GUNICORN_CMD=(
  gunicorn "$WSGI_MODULE"
  --bind "0.0.0.0:$PORT"
  --workers "$WORKERS"
  --pid "$GUNICORN_PID"
  --access-logfile "$LOG_DIR/access.log"
  --error-logfile  "$LOG_DIR/error.log"
  --capture-output
  --daemon
)

# ---------------------------------------------------------------------------
# 8. Launch Gunicorn
# ---------------------------------------------------------------------------
info "=== Starting Gunicorn ($ENV, $WORKERS workers) ==="

if $USE_JOURNALD; then
  # Drop --daemon so journald captures stdout; manage PID manually.
  # Use the full venv path so the subshell doesn't rely on PATH/pyenv shims.
  nohup bash -c "
    $VENV_DIR/bin/gunicorn $WSGI_MODULE \
      --bind 0.0.0.0:$PORT \
      --workers $WORKERS 2>&1 \
    | systemd-cat -t $GUNICORN_TAG -p info
  " &
  echo $! > "$GUNICORN_PID"
else
  "${GUNICORN_CMD[@]}"
fi

sleep 2

# ---------------------------------------------------------------------------
# 9. Health check + summary
# ---------------------------------------------------------------------------
echo ""
info "=== Process summary ==="
if [[ -f "$GUNICORN_PID" ]] && kill -0 "$(cat "$GUNICORN_PID")" 2>/dev/null; then
  ok "Gunicorn is running (PID $(cat "$GUNICORN_PID")) on port $PORT"
else
  warn "Gunicorn does NOT appear to be running — check logs"
fi

echo ""
if $USE_JOURNALD; then
  info "=== Tail logs with journalctl ==="
  echo "  journalctl -t $GUNICORN_TAG -f"
else
  info "=== Tail log files ==="
  echo "  tail -f $LOG_DIR/access.log"
  echo "  tail -f $LOG_DIR/error.log"
  echo "  tail -f $LOG_DIR/*.log"
fi

echo ""
ok "Server started in $ENV mode — http://0.0.0.0:$PORT"
