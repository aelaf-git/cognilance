#!/usr/bin/env bash
# Start the Cognilance Agent Host developer portal (requires registry for agent registration).
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

pip install -q -e . -e agent-host

UI_DIR="$ROOT/agent-host/developer-ui"
STATIC_INDEX="$ROOT/agent-host/src/agent_host/static/index.html"
if [[ ! -f "$STATIC_INDEX" ]]; then
  echo "Building developer portal UI..."
  (cd "$UI_DIR" && npm install && npm run build)
fi

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
  echo "WARNING: Registry is not reachable at ${REGISTRY_URL}" >&2
  echo "Agents can still be uploaded, but will not register until the registry is up." >&2
  echo "Start it with: cd registry && docker compose watch" >&2
else
  echo "  registry ok"
fi

exec python -m agent_host
