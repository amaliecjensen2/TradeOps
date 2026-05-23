# AmalieTrader: En Kubernetes-baseret trading-platform med risikostyring og Interactive Brokers-integration

> Arbejdsudkast til hovedopgave. Tekst markeret med `TODO` skal udfyldes, kontrolleres eller omskrives med egne refleksioner før aflevering.

## Forside

**Titel:** AmalieTrader: En Kubernetes-baseret trading-platform med risikostyring og Interactive Brokers-integration  
**Uddannelse:** Datamatiker  
**Studerende:** Amalie C. Jensen  
**Afleveringsdato:** TODO  
**Vejleder:** TODO  
**Repository:** TODO: Indsæt link til GitHub repository  
**Produktdemo:** TODO: Indsæt link til kort video eller screenshots som bilag

## Resumé

Denne hovedopgave beskriver udviklingen af AmalieTrader, en prototype på en event-drevet trading-platform til algoritmisk handel mod Interactive Brokers. Projektet er ikke udviklet som en enkelt trading-bot, men som en samlet platform, hvor handelsstrategier kan køre som isolerede services, mens ordreflow, broker-integration, risikokontrol, overvågning, datalagring og dashboard håndteres centralt.

Systemet er bygget som en Kubernetes-applikation med flere services. Handelsstrategier sender ordreønsker til en risk gateway, som udfører pre-trade kontroller. Godkendte ordrer publiceres på NATS, hvorefter en central IBKR-adapter samler ordrerne op, oversætter dem til Interactive Brokers API-format og sender dem videre via IB Gateway. Broker-events som fills, positioner og PnL sendes tilbage gennem NATS, hvor risk-monitor, API og dashboard kan anvende dem.

Projektet demonstrerer anvendelse af moderne softwareudviklingsteknikker inden for microservices, containerisering, Kubernetes, event-drevet arkitektur, risikostyring, test og deployment. Produktet er udviklet med Python-services, FastAPI/aiohttp, Pydantic, NATS JetStream, TimescaleDB/PostgreSQL, Next.js og Helm.

## Indholdsfortegnelse

TODO: Genereres automatisk i Word/Google Docs.

## 1. Indledning

Algoritmisk trading stiller høje krav til softwarearkitektur, fordi fejl kan få direkte økonomiske konsekvenser. En simpel trading-bot kan teknisk set sende ordrer direkte til en broker, men en sådan løsning giver begrænset kontrol over risici, logging, fejlhåndtering og driftsstabilitet. I et mere professionelt setup bør strategier ikke selv have direkte adgang til brokerens API. Ordreflowet bør i stedet passere gennem et kontrolleret system, hvor handler kan valideres, logges og overvåges.

AmalieTrader er udviklet som et bud på en sådan platform. Projektet tager udgangspunkt i Interactive Brokers, som tilbyder både paper trading og live trading. Paper trading anvendes som testmiljø, så systemets flow kan afprøves uden at risikere rigtige penge. Arkitekturen er designet, så flere strategier på sigt kan køre parallelt mod samme konto, men med fælles risikostyring og en central broker-adapter.

Projektets fokus er derfor ikke at udvikle den mest avancerede handelsstrategi, men at bygge den infrastruktur, som en handelsstrategi kan køre sikkert i. Dette omfatter blandt andet:

- en strategy service, der genererer ordreønsker,
- en risk gateway, der validerer ordrer før de sendes videre,
- en eventbus til intern kommunikation,
- en central adapter til Interactive Brokers,
- en risk-monitor til overvågning af konto- og driftsrisiko,
- en database til historiske events,
- et dashboard til operationel synlighed,
- deployment med Kubernetes og Helm.

## 2. Problemformulering

Projektets overordnede problemformulering er:

> Hvordan kan der udvikles en Kubernetes-baseret trading-platform, hvor algoritmiske handelsstrategier kan sende ordrer til Interactive Brokers gennem en kontrolleret, observerbar og risikostyret arkitektur?

For at besvare problemformuleringen arbejdes der med følgende underspørgsmål:

1. Hvordan kan ordreflowet designes, så strategier ikke sender ordrer direkte til brokerens API?
2. Hvordan kan pre-trade risikokontrol implementeres som en selvstændig service?
3. Hvordan kan en central adapter isolere integrationen til Interactive Brokers?
4. Hvordan kan NATS anvendes som eventbus mellem services?
5. Hvordan kan systemet deployes og konfigureres med Kubernetes og Helm?
6. Hvordan kan systemets tilstand synliggøres gennem API, dashboard og alerts?
7. Hvilke begrænsninger og risici findes i den nuværende prototype?

## 3. Afgrænsning

Projektet afgrænses til en prototype, der demonstrerer den tekniske platform og det centrale ordreflow. Fokus er på arkitektur, integration, deployment og risikostyring, ikke på at optimere en profitabel trading-strategi.

Følgende indgår i projektet:

- paper trading mod Interactive Brokers,
- eksempelstrategi med simpel moving average-logik,
- risk gateway med pre-trade checks,
- NATS-baseret ordre- og eventflow,
- IBKR-adapter med brokerforbindelse,
- risk-monitor med Telegram-alerts ved drift/risk events,
- Next.js-dashboard til read-only overvågning,
- Kubernetes/Helm deployment.

Følgende er ikke fuldt implementeret i prototypen:

- produktionsklar live trading,
- avanceret strategi-backtesting,
- fuld reconciliation mellem lokal state og broker-state,
- fuld persistent auditlog for alle eventtyper,
- permanent secrets management med ekstern secret manager,
- komplet brugerstyring og adgangskontrol til dashboardet.

Afgrænsningen er vigtig, fordi trading-domænet hurtigt kan blive meget omfattende. Projektet prioriterer derfor den platformsarkitektur, der gør fremtidige strategier og sikkerhedsforanstaltninger mulige.

## 4. Metode og udviklingsproces

Udviklingen er gennemført iterativt med fokus på at få et samlet end-to-end flow til at fungere tidligt. I stedet for først at færdiggøre en enkelt service isoleret, er systemets hovedkomponenter bygget som en samlet vertikal prototype:

```text
Strategi -> Risk Gateway -> NATS -> IBKR Adapter -> IB Gateway -> Interactive Brokers
```

Denne tilgang er valgt, fordi projektets største tekniske risiko ligger i integrationen mellem mange services. Hvis komponenterne først bygges hver for sig, kan man ende med et produkt, hvor de enkelte dele fungerer, men hvor helheden ikke hænger sammen. Ved at bygge et tidligt end-to-end flow blev det muligt løbende at validere arkitekturen.

Arbejdet kan opdeles i følgende faser:

1. Analyse af broker-domænet og Interactive Brokers' begrænsninger.
2. Design af overordnet systemarkitektur.
3. Implementering af Python-services.
4. Implementering af dashboard.
5. Containerisering af services.
6. Kubernetes- og Helm-deployment.
7. Test af centrale dele af ordreflow og risk-logik.
8. Fejlfinding i drift, blandt andet heartbeat timeout og dashboard-data.

TODO: Tilføj egne refleksioner om hvordan du konkret arbejdede uge for uge, hvordan du prioriterede, og hvilke problemer du stødte på.

## 5. Krav og analyse

### 5.1 Funktionelle krav

Systemet skal kunne:

- køre en eller flere strategier som selvstændige services,
- modtage ordreønsker fra strategier,
- validere ordreønsker gennem pre-trade risk checks,
- publicere godkendte ordrer på en intern eventbus,
- sende godkendte ordrer videre til Interactive Brokers via IB Gateway,
- modtage fills, positions- og PnL-events fra brokerintegration,
- overvåge konto- og systemtilstand,
- vise status, PnL, positioner og fills i et dashboard,
- sende alerts ved væsentlige risk- eller driftsproblemer.

### 5.2 Ikke-funktionelle krav

Systemet skal desuden understøtte:

- **modularitet:** services skal kunne udvikles og deployes uafhængigt,
- **observerbarhed:** centrale services skal eksponere health endpoints og metrics,
- **sikkerhed:** strategier bør ikke kunne bypass'e risk gatewayen,
- **konfigurerbarhed:** paper/live mode, risk limits og strategier skal kunne styres via Helm values,
- **driftsvenlighed:** systemet skal kunne køre i Kubernetes,
- **testbarhed:** centrale forretningsregler skal kunne testes uden brokerforbindelse.

### 5.3 Domænespecifikke begrænsninger

Interactive Brokers-domænet har flere begrænsninger, som har påvirket arkitekturen:

- Positioner er knyttet til kontoen og ikke til den enkelte strategi.
- Flere klienter skal bruge unikke `clientId` værdier.
- Brokerforbindelsen er følsom over for reconnects og daglige gateway-restarts.
- Paper trading og live trading bør holdes tydeligt adskilt.
- Strategier skal ikke selv håndtere alle detaljer i IBKR API'et.

Disse forhold gør det hensigtsmæssigt at samle brokerkommunikationen i én central adapter.

## 6. Arkitektur

### 6.1 Overordnet arkitektur

AmalieTrader er bygget som en microservice-baseret platform. Hver service har et afgrænset ansvar:

```text
strategy-hello
  -> risk-gateway
  -> NATS
  -> ibkr-adapter
  -> IB Gateway
  -> Interactive Brokers
```

Den modsatte retning bruges til broker-events:

```text
Interactive Brokers
  -> IB Gateway
  -> ibkr-adapter
  -> NATS
  -> risk-monitor / api / dashboard
```

Den centrale arkitekturbeslutning er, at strategier ikke sender ordrer direkte til IBKR. De sender i stedet ordreønsker til risk-gatewayen. Dette giver systemet et kontrolleret chokepoint, hvor ordrer kan afvises, før de rammer brokerens system.

### 6.2 Strategi-service

`strategy-hello` er en eksempelstrategi. Den er implementeret i Python og bygger på en `BaseStrategy`, som håndterer NATS, HTTP-order submission, health endpoints og metrics. Selve strategien implementerer metoden `on_bar()`.

Den nuværende strategi anvender en simpel moving average-logik:

- Den opbygger en rullende buffer af close-priser.
- Den beregner et hurtigt og et langsomt glidende gennemsnit.
- Hvis det hurtige gennemsnit ligger over det langsomme, sendes et BUY-signal.
- Hvis det hurtige gennemsnit ligger under det langsomme, og strategien er long, sendes et SELL-signal.

Strategien er bevidst simpel. Formålet er ikke at demonstrere en profitabel strategi, men at validere platformens flow fra signal til ordre.

### 6.3 Risk Gateway

Risk-gatewayen er systemets pre-trade kontrol. Den modtager ordreønsker via `POST /orders` og kører en pipeline af checks. Hvis et check fejler, returneres en afvisning, og ordren sendes ikke videre.

De implementerede checks omfatter:

- halt-status,
- restricted symbols,
- fat-finger kontrol for limit-priser,
- maksimum ordre-notional pr. strategi,
- maksimum daily loss pr. strategi,
- maksimum position pr. strategi,
- rate limiting pr. strategi,
- global rate limiting,
- idempotency key for at undgå duplicate orders.

Risk-gatewayen fungerer som en dørmand. Den afgør ikke, om strategien er god, men om en konkret ordre må sendes videre.

En vigtig teknisk begrænsning er, at state i den nuværende version primært holdes in-memory. Det er simpelt og hurtigt, men giver udfordringer ved flere replicas, fordi to pods ikke automatisk deler idempotency-cache, rate-limit state og position state. Dette bør forbedres i en produktionsversion ved at flytte state til Redis, database eller en anden delt state store.

### 6.4 NATS som beskedbus

NATS anvendes som intern beskedbus. Risk-gatewayen sender ikke HTTP direkte til adapteren. I stedet publicerer den godkendte ordrer på et subject:

```text
orders.<strategy>.<symbol>
```

Adapteren lytter på:

```text
orders.>
```

Denne event-drevne tilgang reducerer koblingen mellem services. Risk-gatewayen behøver ikke kende adapterens interne adresse eller levetid. Samtidig kan andre services senere lytte med på de samme events, for eksempel til audit, metrics eller replay.

NATS anvendes også til broker-events såsom:

- `fills.<account>.<symbol>`,
- `positions.<account>.<symbol>`,
- `pnl.<account>`,
- `risk.adapter.heartbeat`,
- `risk.adapter.disconnected`.

### 6.5 Central IBKR-adapter

IBKR-adapteren er den eneste service, der taler direkte med IB Gateway. Den har to hovedopgaver:

1. Modtage interne ordrebeskeder og oversætte dem til IBKR API-kald.
2. Modtage callbacks fra IBKR og publicere dem tilbage på NATS.

Adapteren bygger på `ib_insync`, som er et Python-bibliotek omkring Interactive Brokers API. Når adapteren modtager en ordre, oprettes et IBKR `Contract` og et IBKR `Order` objekt. Derefter sendes ordren til IB Gateway.

Adapteren publicerer også heartbeat-events. Et heartbeat er en lille "jeg lever stadig"-besked, som risk-monitoren bruger til at vurdere, om adapteren stadig er aktiv. Hvis risk-monitoren ikke modtager heartbeat i en bestemt periode, sendes en Telegram-alert.

### 6.6 IB Gateway

IB Gateway er brokerens gateway-applikation. Den kører som en container i Kubernetes og fungerer som mellemled mellem adapteren og Interactive Brokers. Projektet understøtter både paper og live mode, men den aktuelle opsætning anvender paper mode.

At køre IB Gateway i Kubernetes giver en ensartet deploymentmodel, men det skaber også driftsmæssige udfordringer. Gatewayen kræver login, kan kræve 2FA, og skal håndtere brokerens sessioner og reconnects. Derfor er gatewayen placeret som en særskilt komponent i arkitekturen.

### 6.7 Risk Monitor

Risk-monitoren er et out-of-band risikolag. Den står ikke direkte i ordrevejen, men overvåger kontoens tilstand løbende.

Den evaluerer blandt andet:

- dagligt tab,
- drawdown,
- gross exposure,
- adapter heartbeat,
- halt-state.

Risk-monitoren kan sende Telegram-alerts og kan i visse konfigurationer skalere strategy deployments ned til nul via Kubernetes API'et. Da der kan køre flere replicas af risk-monitoren, anvendes Kubernetes Lease-baseret leader election, så kun én replica udfører handlinger.

### 6.8 API og dashboard

API-servicen er en read-only backend til dashboardet. Den eksponerer endpoints for:

- status,
- PnL,
- PnL-historik,
- positioner,
- fills,
- order events.

Dashboardet er bygget i Next.js. Det viser account status, PnL, åbne positioner og seneste fills. Dashboardet er i den nuværende version et overvågningsværktøj, ikke en trading-terminal. Det betyder, at man ikke kan placere handler direkte fra UI'et.

### 6.9 Database

TimescaleDB/PostgreSQL anvendes til historiske data. Databaseskemaet indeholder blandt andet:

- `fills`,
- `pnl_ticks`,
- `positions_snapshot`,
- `order_events`,
- `marketdata_bars`.

TimescaleDB er valgt, fordi tradingdata ofte er tidsseriedata. PnL, market data og fills er alle hændelser, der har en timestamp og ofte skal vises historisk.

## 7. Implementering

### 7.1 Python-services

De fleste backend-services er implementeret i Python. Python er valgt, fordi sproget har et stærkt økosystem for API'er, async I/O, trading-integrationer og hurtig prototyping.

Services anvender blandt andet:

- Pydantic til datamodeller og settings,
- FastAPI/aiohttp til HTTP endpoints,
- NATS Python client til messaging,
- prometheus-client til metrics,
- pytest til unit tests.

Konfiguration sker primært via miljøvariabler. Kubernetes og Helm injicerer disse værdier i pods ved deployment.

### 7.2 Datamodeller

Datamodellerne er defineret som Pydantic-modeller. Det giver typevalidering og en fælles kontrakt mellem services.

Eksempel på en ordre indeholder felter som:

- `strategy`,
- `client_id`,
- `idempotency_key`,
- `symbol`,
- `side`,
- `order_type`,
- `quantity`,
- `limit_price`.

Denne struktur gør det lettere at validere data, før de sendes videre til broker-integration.

### 7.3 Containerisering

Hver service har sin egen Dockerfile. Det betyder, at de kan bygges og pushes som separate images. Images publiceres til GitHub Container Registry.

Fordelen er, at services kan opdateres uafhængigt. En ændring i dashboardet kræver ikke nødvendigvis, at adapteren eller risk-gatewayen bygges om.

### 7.4 Helm chart

Deployment beskrives i `helm/ibkrtrader`. Helm-chartet definerer:

- IB Gateway StatefulSet,
- IBKR adapter Deployment,
- risk-gateway Deployment,
- risk-monitor Deployment og RBAC,
- API Deployment,
- dashboard Deployment,
- NATS dependency,
- TimescaleDB/CloudNativePG resources,
- strategy Deployments genereret fra `values.yaml`.

En vigtig fordel ved Helm er, at strategier kan tilføjes deklarativt:

```yaml
strategies:
  - name: hello
    enabled: true
    clientId: 11
```

På den måde bliver strategier en del af platformens deploymentmodel.

## 8. Test og kvalitetssikring

Projektet indeholder unit tests for flere centrale dele.

### 8.1 Test af strategi

`strategy-hello` testes ved at give strategien kunstige bar-data og mocke `buy()` og `sell()`. På den måde testes signal-logikken uden at sende rigtige ordrer til IBKR.

Eksempler på test:

- SMA kræver nok bars.
- SMA beregnes korrekt.
- Der handles ikke under warmup.
- Stigende priser trigger BUY.
- Faldende priser efter long position trigger SELL.

Under arbejdet blev strategiens test-suite kørt lokalt med resultatet:

```text
6 passed
```

### 8.2 Test af risk gateway

Risk-gatewayens `CheckEngine` testes med unit tests. Testene kontrollerer blandt andet:

- clean order passerer,
- restricted symbol afvises,
- fat-finger price breach afvises,
- notional breach afvises,
- daily loss breach afvises,
- duplicate idempotency key afvises,
- halt flag blokerer alle ordrer.

Disse tests er vigtige, fordi risk-gatewayen er et kritisk sikkerhedslag i systemet.

### 8.3 Test af IBKR-adapter

Adapterens NATS bridge testes ved at simulere order messages. Testene kontrollerer blandt andet, at:

- ordrer droppes, hvis gateway ikke er connected,
- invalid JSON ikke får adapteren til at crashe,
- gyldige ordrer sendes videre til gatewayen, når forbindelsen er aktiv.

### 8.4 Test af risk-monitor

Risk-monitorens circuit breaker testes med cases for:

- daily loss breach,
- drawdown breach,
- gross exposure breach,
- heartbeat timeout,
- allerede halted state.

Heartbeat timeout er testet som alert-only, hvilket betyder at den sender alarm, men ikke nødvendigvis stopper strategier.

### 8.5 End-to-end test

TODO: Beskriv den end-to-end paper test, når den er gennemført.

En relevant end-to-end test for projektet er:

```text
1. Send BUY 1 AAPL MKT som paper order.
2. Verificer at risk-gateway accepterer ordren.
3. Verificer at ordren publiceres på NATS.
4. Verificer at ibkr-adapter sender ordren til IB Gateway.
5. Verificer at IBKR paper account modtager ordren.
6. Verificer fill/position i dashboardet, hvis markedet er åbent og ordren fyldes.
```

Denne test dokumenterer, at hele kæden fra strategi til broker fungerer.

## 9. Drift, observability og alerts

Systemet eksponerer health endpoints som `/healthz` og `/readyz`, hvilket gør det muligt for Kubernetes at vurdere, om pods er levende og klar til trafik.

Der anvendes også Prometheus metrics i flere services. Metrics gør det muligt at overvåge antal ordrer, rejected orders, forbindelsesstatus og andre driftsdata.

Telegram anvendes til alerts. I den nuværende version sendes Telegram-beskeder primært ved risk- og driftshændelser, ikke ved normale fills. Eksempler:

- adapter heartbeat timeout,
- trading halt,
- IBKR connection lost.

Under drift blev der observeret en `ADAPTER HEARTBEAT TIMEOUT`. Det betød, at risk-monitoren ikke havde modtaget heartbeat fra adapteren i længere tid end den konfigurerede grænse. Fejlsøgningen viste, at adapter-podden stadig kunne svare på readiness, men at heartbeat-flowet ikke nødvendigvis var robust nok. Dette er en vigtig læring, fordi en service kan se "grøn" ud for Kubernetes, selv om en intern baggrundstask er stoppet.

## 10. Sikkerhed og risikostyring

Trading-systemer har en særlig risikoprofil, fordi softwarefejl kan føre til uønskede handler. Derfor er risikostyring en central del af projektets design.

De vigtigste sikkerhedsbeslutninger er:

- Strategier taler ikke direkte med IBKR.
- Alle ordrer går gennem risk-gateway.
- Brokerintegration er samlet i én adapter.
- Paper/live mode er adskilt i konfiguration.
- Risk-monitor overvåger kontoens samlede tilstand.
- Telegram alerts bruges til væsentlige drifts- og risk-events.

Der er dog også begrænsninger:

- Risk-gatewayens state er ikke fuldt delt mellem replicas.
- Dashboardet har ikke implementeret brugerlogin.
- Secrets management er ikke produktionsmodent.
- NetworkPolicies er endnu ikke implementeret til at forhindre bypass af risk-gatewayen.
- Heartbeat-tasken i adapteren bør gøres mere robust.

Disse punkter er relevante som perspektivering og forbedringsmuligheder.

## 11. Diskussion

### 11.1 Hvorfor microservices?

Projektet kunne være bygget som en monolit, men microservices passer godt til domænet, fordi komponenterne har tydeligt forskellige ansvar. Strategier, risk-gateway, broker-adapter, dashboard og database har forskellige krav og kan ændre sig uafhængigt.

Ulempen er øget kompleksitet. Der skal håndteres netværk, beskedbus, deployment, logging og observability. I et lille projekt kan det virke tungt, men formålet med hovedopgaven er netop at demonstrere en platform, hvor arkitekturen kan skaleres til flere strategier og mere robust drift.

### 11.2 Hvorfor NATS?

NATS er valgt som intern eventbus, fordi systemet har flere services, der skal kommunikere asynkront. Risk-gatewayen skal ikke nødvendigvis kende adapterens konkrete adresse. Adapteren skal bare lytte på relevante ordre-events.

Eventbus-tilgangen gør det også muligt senere at tilføje audit, replay eller ekstra dashboards uden at ændre den primære ordrevej.

### 11.3 Hvorfor central adapter?

En central adapter reducerer kompleksiteten i strategierne. Hvis hver strategi selv skulle tale med IBKR, skulle hver strategi håndtere:

- broker connection,
- reconnects,
- order IDs,
- IBKR datamodeller,
- fills,
- positioner,
- fejltilstande.

Ved at samle det i adapteren får platformen én broker-integration og én fælles oversættelse mellem interne modeller og IBKR API.

### 11.4 Nuværende teknisk gæld

Projektet er en prototype og har derfor teknisk gæld. De vigtigste punkter er:

- Risk-gateway state bør externaliseres.
- Database migration/deployment skal gøres mere robust.
- Dashboardet bør vise tydeligere fejl, når API-data mangler.
- Adapterens heartbeat-loop bør overvåges bedre.
- Fill/order persistence bør sikres end-to-end.
- Secrets bør håndteres med en mere sikker løsning end lokale secrets.

At identificere disse punkter er en del af projektets faglige refleksion. Det viser, at produktet ikke kun vurderes på hvad der virker, men også på forståelse af hvad der kræves for at gøre det produktionsklart.

## 12. Perspektivering

Projektet kan videreudvikles i flere retninger:

1. **Flere strategier:** Platformen er designet til at kunne køre flere strategy deployments.
2. **Bedre strategiudvikling:** Der kan tilføjes backtesting, paper/live sammenligning og strategi-metrics.
3. **Mere robust risk:** Risk state kan flyttes til Redis eller database, så flere replicas deler samme tilstand.
4. **Fuld audit trail:** Alle ordre-events og broker-callbacks kan gemmes persistent.
5. **NetworkPolicies:** Strategier kan teknisk forhindres i at kontakte IB Gateway direkte.
6. **Brugeradgang:** Dashboardet kan beskyttes med auth, fx Tailscale, OIDC eller reverse proxy.
7. **Bedre alerting:** Telegram kan udvides til fills, rejected orders og reconciliation drift.
8. **Reconciliation:** Systemet kan løbende sammenligne lokal state med brokerens state.

På længere sigt kan platformen også udvides til flere brokers, men det vil kræve en generisk broker-adapter interface og en tydeligere adskillelse mellem broker-specifik og broker-uafhængig logik.

## 13. Konklusion

Projektet har resulteret i en fungerende prototype på en Kubernetes-baseret trading-platform omkring Interactive Brokers. Systemet demonstrerer et kontrolleret ordreflow, hvor strategier sender ordreønsker til en risk gateway, som validerer ordrer før de publiceres på NATS. En central IBKR-adapter håndterer brokerintegrationen, mens risk-monitor, API og dashboard giver overvågning og synlighed.

Projektet besvarer problemformuleringen ved at vise, hvordan en trading-platform kan designes med fokus på risikostyring, modularitet og drift. Arkitekturen gør det muligt at isolere strategier, centralisere brokerkommunikation og indføre flere lag af kontrol.

Samtidig viser projektet, at trading-infrastruktur er komplekst. En prototype kan demonstrere flowet, men en produktionsklar løsning kræver yderligere arbejde med delt state, secrets management, audit logging, reconciliation, adgangskontrol og robust fejlhåndtering.

Den vigtigste læring er, at en sikker trading-løsning ikke bør starte med selve strategien, men med platformen omkring strategien. Strategien er kun den del, der genererer intentionen om at handle. Den afgørende softwaremæssige udfordring ligger i at kontrollere, transportere, udføre, overvåge og dokumentere denne intention på en sikker måde.

## 14. Litteraturliste

TODO: Udfyld med korrekte APA/Harvard referencer. Følgende kilder er relevante:

- Interactive Brokers API documentation.
- Kubernetes documentation.
- Helm documentation.
- NATS documentation.
- FastAPI documentation.
- Next.js documentation.
- TimescaleDB documentation.
- Pydantic documentation.
- KEA/EK studieordning for afsluttende projekt 2025/2026.
- Hovedopgaven - en guide.

## 15. Bilag

TODO: Foreslåede bilag:

- Bilag A: Arkitekturdiagram.
- Bilag B: Screenshot af dashboard.
- Bilag C: Screenshot af Kubernetes pods.
- Bilag D: Eksempel på ordre-payload.
- Bilag E: Testresultater.
- Bilag F: Uddrag af Helm values.
- Bilag G: Link til GitHub repository.
- Bilag H: Link til produktdemo.

