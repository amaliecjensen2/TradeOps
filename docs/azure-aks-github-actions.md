# Azure AKS + GitHub Actions setup

Denne guide beskriver den konkrete opsaetning til dette repo.

## 1) Azure ressourcer

Koer kommandoerne i PowerShell:

```powershell
az login
az account show

# Vaelg abonnement hvis du har flere
az account set --subscription "<subscription-id-eller-navn>"

# Opret resource group
az group create --name amalie-trader-rg --location westeurope

# Opret ACR
az acr create --resource-group amalie-trader-rg --name amalietraderacr --sku Basic

# Opret AKS
az aks create --resource-group amalie-trader-rg --name amalie-trader-aks --node-count 2 --enable-addons monitoring --generate-ssh-keys

# Giv AKS adgang til ACR
az aks update --resource-group amalie-trader-rg --name amalie-trader-aks --attach-acr amalietraderacr
```

## 2) K8s namespace + secrets

```powershell
az aks get-credentials --resource-group amalie-trader-rg --name amalie-trader-aks --overwrite-existing
kubectl create namespace trading

# IBKR login secret (brug dine egne vaerdier)
kubectl -n trading create secret generic ibkrtrader-ibkr-credentials \
  --from-literal=TWS_USERID="<ibkr-user>" \
  --from-literal=TWS_PASSWORD="<ibkr-password>"

# Telegram secret (valgfrit)
kubectl -n trading create secret generic telegram-credentials \
  --from-literal=TELEGRAM_TOKEN="<token>" \
  --from-literal=TELEGRAM_CHAT_ID="<chat-id>"
```

## 3) Service principal til GitHub Actions

```powershell
$SUBSCRIPTION_ID = az account show --query id -o tsv
az ad sp create-for-rbac \
  --name "amalie-trader-gha" \
  --role contributor \
  --scopes "/subscriptions/$SUBSCRIPTION_ID/resourceGroups/amalie-trader-rg" \
  --sdk-auth
```

Gem JSON-outputtet fra kommandoen. Det bliver brugt som GitHub secret.

Hvis du opretter eller roterer secret manuelt i Azure Portal, skal du bruge
secretens **Value** og ikke **Secret ID**. En ugyldig eller udloe bet client secret
giver typisk fejlen `Invalid client secret provided` i `azure/login`.

Hent ACR credentials:

```powershell
az acr show --name amalietraderacr --query loginServer -o tsv
az acr credential show --name amalietraderacr
```

## 4) GitHub repo settings

Under Settings > Secrets and variables > Actions:

Repository secrets:
- `AZURE_CREDENTIALS` = JSON fra service principal
- Alternativt kan du bruge `AZURE_CLIENT_ID`, `AZURE_CLIENT_SECRET`, `AZURE_SUBSCRIPTION_ID`, `AZURE_TENANT_ID`
- `ACR_LOGIN_SERVER` = fx `amalietraderacr.azurecr.io`
- `ACR_USERNAME` = fra `az acr credential show`
- `ACR_PASSWORD` = fra `az acr credential show`

Repository variables:
- `AZURE_RESOURCE_GROUP` = `amalie-trader-rg`
- `AKS_CLUSTER_NAME` = `amalie-trader-aks`
- `AKS_NAMESPACE` = `trading`
- `HELM_RELEASE_NAME` = `trader`

## 5) Hvad workflowet goer

Workflow: `.github/workflows/deploy-aks.yml`

Ved push til `main`:
1. Bygger alle service-images
2. Pusher til ACR
3. Koerer Helm upgrade/install mod AKS
4. Verificerer rollout paa noegle-deployments

## 6) Drift og fejlfinding

```powershell
kubectl -n trading get pods
kubectl -n trading get events --sort-by=.metadata.creationTimestamp
kubectl -n trading logs deploy/trader-ibkrtrader-ibkr-adapter --tail=200
kubectl -n trading logs deploy/trader-ibkrtrader-risk-gateway --tail=200
kubectl -n trading logs deploy/trader-ibkrtrader-api --tail=200
```

Hvis en pod ikke starter:

```powershell
kubectl -n trading describe pod <pod-navn>
```

Hvis GitHub Actions viser `The connection to the server localhost:8080 was refused`,
betyder det normalt, at AKS context/kubeconfig ikke blev sat. Kig på trinnene lige
før `Dump diagnostics on failure`, især Azure login, `AZURE_RESOURCE_GROUP`,
`AKS_CLUSTER_NAME` og service principalens adgang til AKS-clusteret.

Hvis Azure login fejler med `Invalid client secret provided`, er problemet normalt
selve GitHub-secreten og ikke Helm-chartet. Den hurtigste reparation er at oprette
en ny service principal secret eller køre `az ad sp create-for-rbac --sdk-auth`
igen og opdatere `AZURE_CREDENTIALS` med det fulde JSON-output.

## 7) Vigtige noter

- Chartet forventer to strategier i raekkefoelge: hello og nvidia.
- Hvis du flytter eller tilfoejer strategier, skal deploy-kommandoens `strategies[0]` og `strategies[1]` opdateres i workflowet.
- `values.azure.yaml` slukker imagePullSecrets, da AKS normalt kan hente fra tilkoblet ACR direkte.
