# Start Gateway in your own terminal, so it lives as long as the window does.
#
#     .\run.ps1
#
# --no-access-log is not optional. Uvicorn's access log records every visitor's
# IP address, and this platform has no accounts and stores no conversations
# precisely so that no list of who reads or writes here exists. See
# docs/PRIVACY_THREAT_MODEL.md.

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

$python = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) {
    Write-Error "No virtualenv at .venv — run: python -m venv .venv; .venv\Scripts\pip install -r requirements.txt"
}

Write-Host "Gateway starting on http://127.0.0.1:8000  (Ctrl+C to stop)" -ForegroundColor DarkYellow
& $python -m uvicorn app.main:app --port 8000 --no-access-log
