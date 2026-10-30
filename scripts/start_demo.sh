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
  echo "  GEMINI_API_KEY=your_gemini_key" >&2
  exit 1
fi

if ! grep -qE '^(GEMINI_API_KEY|GOOGLE_API_KEY)=.+' .env 2>/dev/null; then
  echo "ERROR: Set GEMINI_API_KEY in .env (free at https://aistudio.google.com/apikey)" >&2
  exit 1
fi

export COGNILANCE_DEMO="${COGNILANCE_DEMO:-1}"
export PYTHONPATH="${ROOT}${PYTHONPATH:+:${PYTHONPATH}}"
export COGNILANCE_APPROVAL_GRADES="${COGNILANCE_APPROVAL_GRADES:-irreversible}"

echo "Installing Python package..."
pip install -q -e .

COORDINATOR_PORT="${COGNILANCE_COORDINATOR_PORT:-${COGNILANCE_ORCHESTRATOR_PORT:-8200}}"
SUPABASE_URL="http://127.0.0.1:54321"
CHAT_DIR="${ROOT}/UIs/chat"

supabase_answers() {
  curl -sS --max-time 2 -o /dev/null "${SUPABASE_URL}/"
}

if supabase_answers; then
  echo "Chat database already running at ${SUPABASE_URL}"
else
  if ! command -v supabase >/dev/null 2>&1; then
    echo "ERROR: The Supabase CLI is missing. Install it, then run: supabase start" >&2
    echo "  https://supabase.com/docs/guides/cli/getting-started" >&2
    exit 1
  fi
  echo "Starting chat database..."
  (cd "${CHAT_DIR}" && supabase start)
fi

for _ in $(seq 1 60); do
  if supabase_answers; then
    break
  fi
  sleep 0.5
done

if ! supabase_answers; then
  echo "ERROR: Chat database did not answer at ${SUPABASE_URL}" >&2
  exit 1
fi

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
echo "  Chat DB: ${SUPABASE_URL}"
echo ""
echo "  Chat UI: cd UIs/chat && npm run dev"
echo "  Share online (free): ./scripts/expose_demo.sh"
echo "  Stop: Ctrl+C"
echo "========================================"
echo ""

wait
