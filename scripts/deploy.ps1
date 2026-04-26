param(
    [Parameter(Mandatory = $true)]
    [string]$DeployPath
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path -LiteralPath $DeployPath)) {
    throw "Deploy path not found: $DeployPath"
}

Set-Location -LiteralPath $DeployPath

Write-Host "Pulling latest code..."
git fetch --all --prune
git checkout main
git pull origin main

Write-Host "Building and starting containers..."
docker compose up -d --build

Write-Host "Waiting for web container health..."
docker compose ps

Write-Host "Deployment finished."
