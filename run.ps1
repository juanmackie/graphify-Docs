# DocGraph — single-command local run (Windows PowerShell)
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

if (-not (Test-Path "backend\.venv")) {
  Write-Host "-> Setting up backend..."
  Push-Location backend
  uv venv .venv
  uv pip install -r requirements.txt
  Pop-Location
}

if (-not (Test-Path "frontend\node_modules")) {
  Write-Host "-> Installing frontend deps..."
  Push-Location frontend
  npm install --no-audit --no-fund
  Pop-Location
}
if (-not (Test-Path "frontend\dist")) {
  Write-Host "-> Building frontend..."
  Push-Location frontend
  npm run build
  Pop-Location
}

Write-Host "-> Starting server on http://localhost:8000"
Push-Location backend
& ".venv\Scripts\python.exe" -m uvicorn app.main:app --host 127.0.0.1 --port 8000
Pop-Location
