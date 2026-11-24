#!/usr/bin/env bash
# Run the Mave desktop app against Mave's computer.
# Reads OS1_ORCHESTRATOR_URL and OS1_CLIENT_TOKEN from desktop.env (gitignored) at the repo root.
set -euo pipefail
cd "$(dirname "$0")/.."
[[ -f desktop.env ]] || { echo "missing desktop.env (OS1_ORCHESTRATOR_URL, OS1_CLIENT_TOKEN)"; exit 1; }
set -a; . ./desktop.env; set +a
[[ -d node_modules ]] || npm install
# This Electron release downloads its binary on first use; make sure it's there before electron-vite starts.
node -e "require('electron')" >/dev/null 2>&1 || node node_modules/electron/install.js
exec npm run dev
