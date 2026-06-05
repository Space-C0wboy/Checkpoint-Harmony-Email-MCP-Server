#!/usr/bin/env pwsh
$ErrorActionPreference = "Stop"
uv venv
uv pip install -e ".[dev]"
Write-Host "Setup complete. Copy .env.example to .env and fill in credentials."
