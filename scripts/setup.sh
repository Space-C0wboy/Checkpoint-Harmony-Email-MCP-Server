#!/usr/bin/env bash
set -euo pipefail
uv venv
uv pip install -e ".[dev]"
echo "Setup complete. Copy .env.example to .env and fill in credentials."
