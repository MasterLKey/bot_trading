# Local start (PowerShell) — uses .env in project root
Set-Location $PSScriptRoot
if (-not (Test-Path .env)) {
    Write-Host "Copy .env.example to .env and fill Alpaca keys first."
    Copy-Item .env.example .env
}
docker compose up -d --build
Write-Host "Dashboard: http://localhost:8000"
