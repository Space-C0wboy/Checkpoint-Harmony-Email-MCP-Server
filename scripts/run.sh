#!/usr/bin/env bash
set -euo pipefail
# Usage: scripts/run.sh            # stdio
#        scripts/run.sh http 8765  # http on port
if [ "${1:-stdio}" = "http" ]; then
  exec uv run checkpoint-harmony-mcp --transport http --port "${2:-8765}"
fi
exec uv run checkpoint-harmony-mcp
