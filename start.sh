#!/usr/bin/env bash
# Start the live API, static UI, native model worker and isolated runner together.
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
[[ -d "$CODEJURY_MODEL_DIR" ]] || fail 'Local model weights are missing. Follow the setup instructions in README.md.'
[[ -f "$CODEJURY_ADAPTER_DIR/adapters.safetensors" ]] || fail 'The trained Fixer A adapter is missing. See README.md; cloning does not include weights.'
PORT="${CODEJURY_PORT:-8000}"
"$PYTHON" - "$PORT" <<'PY'
import socket, sys
port = int(sys.argv[1])
if not 1 <= port <= 65535:
    raise SystemExit('CODEJURY_PORT must be between 1 and 65535')
with socket.socket() as sock:
    try:
        sock.bind(('127.0.0.1', port))
    except OSError:
        raise SystemExit(f'Port {port} is occupied. Stop the existing server or set CODEJURY_PORT.')
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
echo "CodeJury is ready: $URL"
echo 'Press Ctrl+C to stop the app. The dedicated sandbox VM stays available.'
if [[ "$NO_OPEN" == 0 ]]; then open "$URL"; fi
wait "$SERVER_PID"
