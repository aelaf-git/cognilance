#!/usr/bin/env bash
# Start the full Cognilance demo stack locally (registry + agents + orchestrator).
# Use scripts/expose_demo.sh to share it on the internet for free via Cloudflare Tunnel.
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
  echo "  COGNILANCE_REGISTRY_URL=http://127.0.0.1:8088" >&2
  exit 1
fi

if ! grep -q '^GROQ_API_KEY=.\+' .env 2>/dev/null; then
  echo "ERROR: Set GROQ_API_KEY in .env (free at https://console.groq.com)" >&2
  exit 1
fi

echo "Installing Python packages..."
pip install -q -e . -e orchestrator -r agents/email_writer/requirements.txt

REGISTRY_URL="${COGNILANCE_REGISTRY_URL:-http://127.0.0.1:8088}"
REGISTRY_HEALTH="${REGISTRY_URL%/}/health"
ORCHESTRATOR_PORT="${COGNILANCE_ORCHESTRATOR_PORT:-8200}"

PIDS=()
cleanup() {
  echo ""
  echo "Stopping demo..."
  for pid in "${PIDS[@]}"; do
    kill "$pid" 2>/dev/null || true
  done
  if [[ "${KEEP_REGISTRY:-}" != "1" ]]; then
    (cd registry && docker compose down) 2>/dev/null || true
  fi
}
trap cleanup EXIT INT TERM

if ! curl -sf "${REGISTRY_HEALTH}" >/dev/null 2>&1; then
  echo "Starting registry (Docker)..."
  if ! command -v docker >/dev/null 2>&1; then
    echo "ERROR: Docker is required. Install Docker or start the registry manually." >&2
    exit 1
  fi
  (cd registry && docker compose up -d --build)
  echo "Waiting for registry..."
  for _ in $(seq 1 60); do
    if curl -sf "${REGISTRY_HEALTH}" >/dev/null; then
      break
    fi
    sleep 1
  done
fi

if ! curl -sf "${REGISTRY_HEALTH}" >/dev/null; then
  echo "ERROR: Registry not reachable at ${REGISTRY_URL}" >&2
  exit 1
fi
echo "Registry ok: ${REGISTRY_URL}"

echo "Starting agents..."
python -u agents/email_writer/agent.py &
PIDS+=($!)

for port in 8101; do
  for _ in $(seq 1 60); do
    if curl -sf "http://127.0.0.1:${port}/health" >/dev/null; then
      echo "  agent :${port} ok"
      break
    fi
    sleep 0.5
  done
done

echo "Starting orchestrator..."
cognilance-orchestrator &
PIDS+=($!)

for _ in $(seq 1 60); do
  if curl -sf "http://127.0.0.1:${ORCHESTRATOR_PORT}/health" >/dev/null; then
    break
  fi
  sleep 0.5
done

echo ""
echo "========================================"
echo "  Cognilance demo is running locally"
echo "========================================"
echo "  Chat UI:  http://127.0.0.1:${ORCHESTRATOR_PORT}/chat"
echo "  Health:   http://127.0.0.1:${ORCHESTRATOR_PORT}/health"
echo "  Registry: ${REGISTRY_URL}"
echo ""
echo "  Share online (free): ./scripts/expose_demo.sh"
echo "  Stop: Ctrl+C"
echo "========================================"
echo ""

wait
