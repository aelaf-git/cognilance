#!/usr/bin/env bash
# Start every marketplace agent under agents/*/agent.py.
# Requires the registry at COGNILANCE_REGISTRY_URL (default http://127.0.0.1:8088).
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

mapfile -t AGENT_DIRS < <(
  find agents -mindepth 2 -maxdepth 2 -type f -name agent.py | sed 's|/agent\.py$||' | sort
)

if [[ ${#AGENT_DIRS[@]} -eq 0 ]]; then
  echo "ERROR: No agents/*/agent.py found under agents/" >&2
  exit 1
fi

REQS=()
for dir in "${AGENT_DIRS[@]}"; do
  if [[ -f "${dir}/requirements.txt" ]]; then
    REQS+=(-r "${dir}/requirements.txt")
  fi
done

echo "Installing agent packages (${#AGENT_DIRS[@]} agent(s))..."
pip install -q -e . "${REQS[@]}"

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
  echo ""
  echo "Stopping agents..."
  for pid in "${PIDS[@]}"; do
    kill "$pid" 2>/dev/null || true
  done
  wait 2>/dev/null || true
}
trap cleanup EXIT INT TERM

echo "Starting ${#AGENT_DIRS[@]} agent(s)..."
for dir in "${AGENT_DIRS[@]}"; do
  name="$(basename "${dir}")"
  port="$(
    sed -nE 's/.*port[[:space:]]*=[[:space:]]*([0-9]+).*/\1/p' "${dir}/agent.py" | head -1
  )"
  # Run from the agent folder so local imports (scrape.py, proxy.py, …) resolve.
  echo "  ${name}${port:+ (:${port})} ← ${dir}/agent.py"
  (
    cd "${dir}"
    python -u agent.py
  ) &
  PIDS+=($!)
done

# Wait briefly for health endpoints when ports are declared.
for dir in "${AGENT_DIRS[@]}"; do
  port="$(
    sed -nE 's/.*port[[:space:]]*=[[:space:]]*([0-9]+).*/\1/p' "${dir}/agent.py" | head -1
  )"
  [[ -z "${port}" ]] && continue
  ready=false
  for _ in $(seq 1 40); do
    if curl -sf "http://127.0.0.1:${port}/health" >/dev/null; then
      echo "  agent :${port} ok"
      ready=true
      break
    fi
    sleep 0.25
  done
  if [[ "${ready}" != "true" ]]; then
    echo "  warning: agent :${port} did not become healthy yet" >&2
  fi
done

echo ""
echo "Agents running (Ctrl+C to stop all)."
wait
