#!/usr/bin/env bash
# Expose the local orchestrator chat UI on the internet for free (Cloudflare quick tunnel).
# Requires: demo already running (./scripts/start_demo.sh) and cloudflared installed.
set -euo pipefail

ORCHESTRATOR_PORT="${COGNILANCE_ORCHESTRATOR_PORT:-8200}"
LOCAL_URL="http://127.0.0.1:${ORCHESTRATOR_PORT}"

if ! curl -sf "${LOCAL_URL}/health" >/dev/null; then
  echo "ERROR: Orchestrator is not running at ${LOCAL_URL}" >&2
  echo "Start the demo first: ./scripts/start_demo.sh" >&2
  exit 1
fi

if ! command -v cloudflared >/dev/null 2>&1; then
  echo "cloudflared is not installed." >&2
  echo "" >&2
  echo "Install it (pick one):" >&2
  echo "  Linux:  https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/" >&2
  echo "  macOS:  brew install cloudflared" >&2
  echo "  Debian: sudo apt install cloudflared" >&2
  exit 1
fi

echo "Opening a free public URL for ${LOCAL_URL}/chat ..."
echo "(Your laptop must stay on. Tunnel closes when this script stops.)"
echo ""

cloudflared tunnel --url "${LOCAL_URL}"
