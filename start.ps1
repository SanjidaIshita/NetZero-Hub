# Starts the Recycling Collection Scheduling stack with Docker Compose.
# Refreshes PATH for this PowerShell session first, so `docker` is found even in a
# terminal opened before Docker Desktop was installed or updated.

$win = $env:WINDIR
$env:Path = @(
    "$win\System32", $win, "$win\System32\Wbem", "$win\System32\WindowsPowerShell\v1.0\",
    [Environment]::GetEnvironmentVariable("Path", "Machine"),
    [Environment]::GetEnvironmentVariable("Path", "User")
) -join ";"

Set-Location $PSScriptRoot

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Write-Host "Docker CLI not found. Install Docker Desktop, then run this script again." -ForegroundColor Red
    return
}
docker info --format "{{.ServerVersion}}" *> $null
if ($LASTEXITCODE -ne 0) {
    Write-Host "Docker Desktop is not running. Start it, wait for 'Engine running', then run this script again." -ForegroundColor Yellow
    return
}
if (-not (Test-Path .env)) {
    Write-Host "No .env file. Copy .env.example to .env and fill in the CHANGE-ME values." -ForegroundColor Red
    return
}

docker compose up -d
docker compose ps
Write-Host ""
Write-Host "App:      http://localhost:3000" -ForegroundColor Green
Write-Host "API docs: http://localhost:3000/api/docs/" -ForegroundColor Green
