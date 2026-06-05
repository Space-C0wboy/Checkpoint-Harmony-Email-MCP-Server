#!/usr/bin/env pwsh
param(
    [string]$Transport = "stdio",
    [int]$Port = 8765
)
$ErrorActionPreference = "Stop"
# Usage: scripts\run.ps1            # stdio
#        scripts\run.ps1 http 8765  # http on port
if ($Transport -eq "http") {
    uv run checkpoint-harmony-mcp --transport http --port $Port
} else {
    uv run checkpoint-harmony-mcp
}
