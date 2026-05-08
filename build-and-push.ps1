# build-and-push.ps1
# Builds all ibkrtrader service images and pushes to ghcr.io.
#
# Usage:
#   .\build-and-push.ps1 -GithubUser <dit-github-brugernavn> [-Tag v0]
#
# Requirements:
#   - Docker Desktop running
#   - Already logged in: docker login ghcr.io
#
param(
    [Parameter(Mandatory=$true)]
    [string]$GithubUser,

    [string]$Tag = "v0"
)

$ErrorActionPreference = "Stop"
$Registry = "ghcr.io/$($GithubUser.ToLower())"
$Root = $PSScriptRoot

$Services = @(
    "ibkr-adapter",
    "risk-monitor",
    "risk-gateway",
    "api",
    "strategy-hello",
    "dashboard"
)

Write-Host "Registry: $Registry" -ForegroundColor Cyan
Write-Host "Tag:      $Tag" -ForegroundColor Cyan
Write-Host ""

foreach ($svc in $Services) {
    $context = Join-Path $Root "services\$svc"
    $image   = "$Registry/ibkrtrader/${svc}:$Tag"

    Write-Host "--- Building $svc ---" -ForegroundColor Yellow
    docker build -t $image $context
    if ($LASTEXITCODE -ne 0) { throw "Build failed for $svc" }

    Write-Host "--- Pushing $svc ---" -ForegroundColor Yellow
    docker push $image
    if ($LASTEXITCODE -ne 0) { throw "Push failed for $svc" }

    Write-Host "OK: $image" -ForegroundColor Green
    Write-Host ""
}

Write-Host "All images built and pushed." -ForegroundColor Green
Write-Host ""
Write-Host "Next: update values.yaml imageRegistry to:" -ForegroundColor Cyan
Write-Host "  $Registry" -ForegroundColor White
Write-Host ""
Write-Host "Then deploy:" -ForegroundColor Cyan
Write-Host "  helm install trader ./helm/ibkrtrader -f helm/ibkrtrader/values.paper.yaml -n trading --set global.imageRegistry=$Registry" -ForegroundColor White
