#!/usr/bin/env bash
set -e

BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$BASE_DIR"

if [ -d ".venv" ]; then
    source .venv/bin/activate
fi

exec python3 main.py
