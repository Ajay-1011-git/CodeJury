#!/usr/bin/env bash
# Start the live API, static UI, native model worker and isolated runner together.
# The dashboard runs the Stage 2 jury (Fixer A/B, Critic, Judge), served under /s2.
set -euo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT/backend"
NO_OPEN=0
case "${1:-}" in
  --no-open) NO_OPEN=1 ;;
  --help|-h) echo 'Usage: ./start.sh [--no-open]'; exit 0 ;;
  '') ;;
  *) echo "Unknown option: $1" >&2; exit 1 ;;
esac
fail() { echo "CodeJury: $*" >&2; exit 1; }
[[ "$(uname -s)" == Darwin && "$(uname -m)" == arm64 ]] || fail 'Live Stage 1 requires an Apple Silicon Mac.'
for tool in colima docker; do command -v "$tool" >/dev/null || fail "Install $tool first (see README.md)."; done
if [[ ! -x .venv/bin/python ]]; then
  command -v uv >/dev/null || fail 'Install uv first (see README.md).'
  uv sync --frozen --python 3.11 --extra model
fi
PYTHON="$ROOT/backend/.venv/bin/python"
export CODEJURY_MODEL_DIR="${CODEJURY_MODEL_DIR:-$ROOT/backend/models/Phi4-mini}"
export CODEJURY_ADAPTER_DIR="${CODEJURY_ADAPTER_DIR:-$ROOT/backend/artifacts/training/fixer_a_selected}"
export CODEJURY_ALLOW_RAW=0
export CODEJURY_PROFILE=stage1-demo
export CODEJURY_STAGE2=1
# Verified Stage 2 runner image (integration/stage2/HANDOFF.md); rebuild with integration/stage2/build_runner.py.
export CODEJURY_STAGE2_RUNNER_IMAGE="${CODEJURY_STAGE2_RUNNER_IMAGE:-sha256:3a0eda85cef3c470ee50838c2d4c0d5208ad0debc2c9578e90ae91677227d61f}"
[[ -d "$CODEJURY_MODEL_DIR" ]] || fail 'Local model weights are missing. Follow the setup instructions in README.md.'
[[ -f "$CODEJURY_ADAPTER_DIR/adapters.safetensors" ]] || fail 'The trained Fixer A adapter is missing. See README.md; cloning does not include weights.'
PORT="${CODEJURY_PORT:-8000}"
[[ "$PORT" =~ ^[0-9]+$ ]] && (( PORT >= 1 && PORT <= 65535 )) || fail 'CODEJURY_PORT must be between 1 and 65535'
# Free the port by stopping whatever is listening on it (SIGTERM, then SIGKILL after 5s).
PIDS="$(lsof -nP -t -iTCP:"$PORT" -sTCP:LISTEN 2>/dev/null || true)"
if [[ -n "$PIDS" ]]; then
  echo "Port $PORT is occupied; stopping the existing process(es):"
  for pid in $PIDS; do echo "  $pid $(ps -o command= -p "$pid" 2>/dev/null || true)"; done
  kill -TERM $PIDS 2>/dev/null || true
  for _ in {1..10}; do
    lsof -nP -t -iTCP:"$PORT" -sTCP:LISTEN >/dev/null 2>&1 || break
    sleep 0.5
  done
  PIDS="$(lsof -nP -t -iTCP:"$PORT" -sTCP:LISTEN 2>/dev/null || true)"
  [[ -z "$PIDS" ]] || kill -KILL $PIDS 2>/dev/null || true
fi
"$PYTHON" - "$PORT" <<'PY'
import socket, sys, time
port = int(sys.argv[1])
for _ in range(10):
    with socket.socket() as sock:
        try:
            sock.bind(('127.0.0.1', port))
            break
        except OSError:
            time.sleep(0.5)
else:
    raise SystemExit(f'Port {port} is still occupied and could not be freed. Stop it manually or set CODEJURY_PORT.')
PY
if ! colima status codejury-stage1 >/dev/null 2>&1; then
  echo 'Starting the dedicated CodeJury sandbox...'
  colima start codejury-stage1 --arch aarch64 --vm-type vz --cpus 2 --memory 2 --disk 10 --mount none --activate=false --ssh-agent=false --ssh-config=false --dns 1.1.1.1 --dns 8.8.8.8
fi
"$PYTHON" - <<'PY'
from codejury.models.worker import readiness
health = readiness()
if not all(health[k] for k in ('model_ready', 'sandbox_ready', 'fixer_a_trained')):
    raise SystemExit(f'Live prerequisites failed: {health}. See README.md for model/adapter/runner setup.')
PY
SERVER_PID=''
cleanup() {
  trap - EXIT INT TERM
  if [[ -n "$SERVER_PID" ]]; then
    kill -TERM "$SERVER_PID" 2>/dev/null || true
    wait "$SERVER_PID" 2>/dev/null || true
  fi
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
"$PYTHON" -m uvicorn codejury.api.app:app --host 127.0.0.1 --port "$PORT" &
SERVER_PID=$!
URL="http://127.0.0.1:$PORT"
"$PYTHON" - "$URL" "$SERVER_PID" <<'PY'
import json, os, sys, time, urllib.request
for _ in range(60):
    try:
        os.kill(int(sys.argv[2]), 0)
    except ProcessLookupError:
        raise SystemExit('The API exited during startup; see its error above.')
    try:
        with urllib.request.urlopen(sys.argv[1] + '/health', timeout=2) as response:
            health = json.load(response)
        if health['runtime_mode'] != 'live' or not all(health[k] for k in ('model_ready', 'sandbox_ready', 'fixer_a_trained')):
            raise SystemExit(f'Live health check failed: {health}')
        break
    except OSError:
        time.sleep(0.5)
else:
    raise SystemExit('The API did not become ready in time.')
PY
"$PYTHON" - "$URL" <<'PY'
import json, sys, urllib.request
try:
    with urllib.request.urlopen(sys.argv[1] + '/s2/health', timeout=30) as response:
        health = json.load(response)
except Exception as exc:
    raise SystemExit(f'The Stage 2 jury did not start ({exc}). Check the runner image and trained adapters (integration/stage2/HANDOFF.md).')
if not health.get('full_stage2_ready'):
    raise SystemExit('The Stage 2 jury is not ready: ' + json.dumps(health))
print('Jury ready (trained roles: ' + ', '.join(health.get('trained_roles', [])) + ')')
PY
echo "CodeJury is ready: $URL"
echo 'Press Ctrl+C to stop the app. The dedicated sandbox VM stays available.'
if [[ "$NO_OPEN" == 0 ]]; then open "$URL"; fi
wait "$SERVER_PID"
