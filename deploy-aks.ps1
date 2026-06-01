param(
    [Parameter(Mandatory = $true)]
    [string]$AcrLoginServer,

    [string]$Tag = "latest",
    [string]$Namespace = "trading",
    [string]$ReleaseName = "trader"
)

$ErrorActionPreference = "Stop"

Write-Host "Deploying release '$ReleaseName' to namespace '$Namespace' with tag '$Tag'" -ForegroundColor Cyan

helm dependency update ./helm/ibkrtrader

helm upgrade --install $ReleaseName ./helm/ibkrtrader `
  --namespace $Namespace `
  --create-namespace `
  -f ./helm/ibkrtrader/values.paper.yaml `
  -f ./helm/ibkrtrader/values.azure.yaml `
  --set-string ibkrAdapter.image.repository="$AcrLoginServer/ibkrtrader/ibkr-adapter" `
  --set-string ibkrAdapter.image.tag="$Tag" `
  --set-string riskGateway.image.repository="$AcrLoginServer/ibkrtrader/risk-gateway" `
  --set-string riskGateway.image.tag="$Tag" `
  --set-string riskMonitor.image.repository="$AcrLoginServer/ibkrtrader/risk-monitor" `
  --set-string riskMonitor.image.tag="$Tag" `
  --set-string api.image.repository="$AcrLoginServer/ibkrtrader/api" `
  --set-string api.image.tag="$Tag" `
  --set-string dashboard.image.repository="$AcrLoginServer/ibkrtrader/dashboard" `
  --set-string dashboard.image.tag="$Tag" `
  --set-string strategies[0].image.repository="$AcrLoginServer/ibkrtrader/strategy-hello" `
  --set-string strategies[0].image.tag="$Tag" `
  --set-string strategies[1].image.repository="$AcrLoginServer/ibkrtrader/strategy-nvidia" `
  --set-string strategies[1].image.tag="$Tag"

kubectl -n $Namespace get pods
