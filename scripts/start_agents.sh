#!/usr/bin/env bash
# Start all Cognilance showcase agents (requires registry at COGNILANCE_REGISTRY_URL).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [[ -f .venv/bin/activate ]]; then
  # shellcheck disable=SC1091
  source .venv/bin/activate
fi

pip install -q -e . -r agents/requirements.txt

REGISTRY_URL="${COGNILANCE_REGISTRY_URL:-http://127.0.0.1:8088}"
REGISTRY_HEALTH="${REGISTRY_URL%/}/health"

echo "Checking registry at ${REGISTRY_URL}..."
registry_ok=false
for _ in $(seq 1 30); do
  if curl -sf "${REGISTRY_HEALTH}" >/dev/null; then
    registry_ok=true
    break
  fi
  sleep 0.5
done

if [[ "${registry_ok}" != "true" ]]; then
  echo "ERROR: Registry is not reachable at ${REGISTRY_URL}" >&2
  echo "Start it first:" >&2
  echo "  cd registry && docker compose watch" >&2
  exit 1
fi
echo "  registry ok"

PIDS=()
cleanup() {
  for pid in "${PIDS[@]}"; do
    kill "$pid" 2>/dev/null || true
  done
}
trap cleanup EXIT INT TERM

python -u agents/research_agent.py &
PIDS+=($!)
python -u agents/data_analyst.py &
PIDS+=($!)
python -u agents/python_code_writer.py &
PIDS+=($!)

echo "Waiting for agents..."
for port in 8101 8102 8103; do
  for _ in $(seq 1 30); do
    if curl -sf "http://127.0.0.1:${port}/health" >/dev/null; then
      echo "  :${port} ok"
      break
    fi
    sleep 0.5
  done
done

echo "Agents running (Ctrl+C to stop all)."
wait
