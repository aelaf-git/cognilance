#!/usr/bin/env bash
# Start Cognilance demo: durable coordinator + specialists (no registry / A2A workers).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [[ -f venv/bin/activate ]]; then
  # shellcheck disable=SC1091
  source venv/bin/activate
elif [[ -f .venv/bin/activate ]]; then
  # shellcheck disable=SC1091
  source .venv/bin/activate
fi

if [[ ! -f .env ]]; then
  echo "Missing .env — create one with at least:" >&2
  echo "  GROQ_API_KEY=your_groq_key" >&2
  exit 1
fi

if ! grep -q '^GROQ_API_KEY=.\+' .env 2>/dev/null; then
  echo "ERROR: Set GROQ_API_KEY in .env (free at https://console.groq.com)" >&2
  exit 1
fi

export COGNILANCE_DEMO="${COGNILANCE_DEMO:-1}"
export PYTHONPATH="${ROOT}${PYTHONPATH:+:${PYTHONPATH}}"
export COGNILANCE_APPROVAL_GRADES="${COGNILANCE_APPROVAL_GRADES:-irreversible}"

echo "Installing Python package..."
pip install -q -e .

COORDINATOR_PORT="${COGNILANCE_COORDINATOR_PORT:-${COGNILANCE_ORCHESTRATOR_PORT:-8200}}"

PIDS=()
cleanup() {
  echo ""
  echo "Stopping demo..."
  for pid in "${PIDS[@]}"; do
    kill "$pid" 2>/dev/null || true
  done
}
trap cleanup EXIT INT TERM

echo "Starting coordinator (in-process specialists)..."
cognilance-coordinator &
PIDS+=($!)

for _ in $(seq 1 60); do
  if curl -sf "http://127.0.0.1:${COORDINATOR_PORT}/health" >/dev/null; then
    break
  fi
  sleep 0.5
done

echo ""
echo "========================================"
echo "  Cognilance demo is running locally"
echo "========================================"
echo "  Health:  http://127.0.0.1:${COORDINATOR_PORT}/health"
echo "  Roles:   http://127.0.0.1:${COORDINATOR_PORT}/skills/online"
echo ""
echo "  Share online (free): ./scripts/expose_demo.sh"
echo "  Stop: Ctrl+C"
echo "========================================"
echo ""

wait
