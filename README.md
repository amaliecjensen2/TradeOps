# TradeOps
Dette er et algoritmisk handelssystem jeg har bygget til at handle aktier automatisk via Interactive Brokers. Systemet kører på Kubernetes.

## Hvad gør det?

Systemet forbinder til Interactive Brokers Gateway, henter markedsdata i realtid, og sender ordrer igennem automatisk baseret på de strategier jeg har defineret. Alt kører i containere og deployes med Helm.

To strategier
- **strategy hello**
  En simpel moving average crossover strategi der handler AAPL
- **strategy nvidia**
  Køber en NVDA aktie og holder den

## Hvordan er det bygget?

Systemet er delt op i en række microservices der taler sammen via NATS:

- **ibkr adapter** forbinder til IB Gateway og videresender markedsdata og ordrer
- **risk gateway** tjekker alle ordrer inden de sendes, så man ikke handler for meget eller taber for mange penge
- **risk monitor** holder øje med den samlede konto og kan slukke for strategierne hvis noget går galt
- **api** REST API til at se positioner, ordrer og PnL
- **dashboard** et Next.js dashboard man kan åbne i browseren

