$ErrorActionPreference = "Stop"
Set-Location -LiteralPath $PSScriptRoot

& kubectl -n trading port-forward svc/trader-ibkrtrader-dashboard 3000:3000 --address 127.0.0.1 *> dashboard-portforward.log
