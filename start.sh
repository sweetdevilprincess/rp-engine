#!/usr/bin/env bash
# RP Engine — Setup & Launch Script
# Usage: bash start.sh [--rebuild]

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

REBUILD=false
for arg in "$@"; do
  case "$arg" in
    --rebuild) REBUILD=true ;;
  esac
done

# ── Check Python ──────────────────────────────────────────
PYTHON=""
for cmd in python3 python; do
  if command -v "$cmd" &>/dev/null; then
    ver=$("$cmd" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>/dev/null || true)
    major=$(echo "$ver" | cut -d. -f1)
    minor=$(echo "$ver" | cut -d. -f2)
    if [ "$major" -ge 3 ] && [ "$minor" -ge 12 ] 2>/dev/null; then
      PYTHON="$cmd"
      echo "✓ Found $cmd $ver"
      break
    fi
  fi
done

if [ -z "$PYTHON" ]; then
  echo "✗ Python 3.12+ is required. Install from https://python.org"
  exit 1
fi

# ── Create venv if needed ─────────────────────────────────
if [ ! -d ".venv" ]; then
  echo "→ Creating virtual environment..."
  "$PYTHON" -m venv .venv
fi

# Activate venv
if [ -f ".venv/Scripts/activate" ]; then
  source .venv/Scripts/activate  # Windows Git Bash
else
  source .venv/bin/activate      # Linux/macOS
fi
echo "✓ Virtual environment active"

# ── Install Python deps ───────────────────────────────────
echo "→ Installing Python dependencies..."
pip install -q -e . 2>&1 | tail -1

# ── Build frontend ────────────────────────────────────────
if [ "$REBUILD" = true ] || [ ! -f "frontend/build/index.html" ]; then
  if ! command -v node &>/dev/null; then
    echo "✗ Node.js is required to build the frontend. Install from https://nodejs.org"
    echo "  (Or run with a pre-built frontend/build/ directory)"
    exit 1
  fi
  echo "→ Building frontend..."
  cd frontend
  npm install --silent 2>&1 | tail -1
  npm run build 2>&1 | tail -3
  cd ..
  echo "✓ Frontend built"
else
  echo "✓ Frontend build exists (use --rebuild to force)"
fi

# ── Start server ──────────────────────────────────────────
PORT=${PORT:-3000}
echo ""
echo "═══════════════════════════════════════════"
echo "  RP Engine starting on http://localhost:$PORT"
echo "═══════════════════════════════════════════"
echo ""

# Open browser after server is ready (polls in background)
"$PYTHON" open_browser.py "$PORT" &

rp-engine --port "$PORT"
