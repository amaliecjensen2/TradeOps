# AmalieTrader

Et algoritmisk handelssystem jeg har bygget til at handle aktier automatisk via Interactive Brokers. Systemet kører på Kubernetes og er sat op til at kunne køre flere strategier på samme tid.

## Hvad gør det?

Systemet forbinder til Interactive Brokers Gateway, henter markedsdata i realtid, og sender ordrer igennem automatisk baseret på de strategier jeg har defineret. Alt kører i containere og deployes med Helm.

Der er lige nu to strategier:
- **strategy-hello** — en simpel moving average crossover strategi der handler AAPL
- **strategy-nvidia** — køber én NVDA-aktie og holder den

## Hvordan er det bygget?

Systemet er delt op i en række microservices der taler sammen via NATS (en message bus):

- **ibkr-adapter** — forbinder til IB Gateway og videresender markedsdata og ordrer
- **risk-gateway** — tjekker alle ordrer inden de sendes, så man ikke handler for meget eller taber for mange penge
- **risk-monitor** — holder øje med den samlede konto og kan slukke for strategierne hvis noget går galt
- **api** — REST API til at se positioner, ordrer og PnL
- **dashboard** — et Next.js dashboard man kan åbne i browseren

Data gemmes i TimescaleDB (en PostgreSQL-variant der er god til tidsseriedata).

## Forudsætninger

- Docker Desktop
- kubectl + Helm
- En Interactive Brokers konto med IB Gateway
- Et Kubernetes cluster (f.eks. lokal med kind eller k3s)

## Deploy

```powershell
# Byg og push images
.\build-and-push.ps1 -GithubUser <dit-github-brugernavn>

# Deploy til paper trading
helm install trader ./helm/ibkrtrader `
  -f helm/ibkrtrader/values.paper.yaml `
  -n trading
```

## Tilføj en ny strategi

Kopier `services/strategy-hello/` til en ny mappe, ret logikken i `strategy.py`, og tilføj en ny entry i `helm/ibkrtrader/values.yaml` under `strategies:`. Husk at give den et unikt `clientId`.
