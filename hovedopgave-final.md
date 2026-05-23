# AmalieTrader: En Kubernetes-baseret trading-platform med risikostyring og Interactive Brokers-integration

## Forside

**Titel:** AmalieTrader: En Kubernetes-baseret trading-platform med risikostyring og Interactive Brokers-integration  
**Uddannelse:** Datamatiker  
**Institution:** Erhvervsakademi København  
**Studerende:** Amalie Colstrup Jensen  
**Vejleder:** Bjørn  
**Afleveringsdato:** TODO: indsæt afleveringsdato  
**Antal anslag:** TODO: opdater efter sidste korrektur  
**Projekt:** AmalieTrader  
**Repository:** https://github.com/amaliecjensen/AmalieTrader  
**Produktstatus:** Prototype til paper trading og teknisk validering

## Resumé

Denne hovedopgave beskriver udviklingen af AmalieTrader, en containerbaseret trading-platform til algoritmisk handel via Interactive Brokers. Projektet tager udgangspunkt i et praktisk problem: en handelsstrategi kan relativt let bygges som en enkelt bot, der sender ordrer direkte til en broker, men en sådan løsning giver begrænset kontrol over risiko, sporbarhed, deployment, fejlhåndtering og drift. Når software kan placere ordrer på en investeringskonto, bliver arkitektur og sikkerhed en central del af produktet.

AmalieTrader er derfor udviklet som en platform frem for en enkelt handelsstrategi. Strategier kører som selvstændige services, som sender ordreintentioner til en Risk Gateway. Risk Gatewayen udfører pre-trade kontroller og publicerer accepterede ordrer på NATS. En central IBKR-adapter modtager ordrebeskederne, oversætter dem til Interactive Brokers' API-model og sender dem videre gennem IB Gateway. Brokerens tilbagemeldinger om fills, positioner, PnL og forbindelsesstatus publiceres tilbage på NATS, hvor risk-monitor, API og dashboard kan bruge dem.

Projektet demonstrerer anvendelse af moderne softwareudviklingsteknikker inden for microservices, containerisering, Kubernetes, Helm, event-drevet arkitektur, API-design, Pydantic-validering, risikostyring, observability og test. Løsningen er skrevet som en v0-prototype med fokus på paper trading. Den er ikke en færdig produktionsplatform til live trading, men den etablerer en teknisk arkitektur, hvor handelsstrategier kan testes mere kontrolleret end i en simpel bot.

En væsentlig konklusion er, at en trading-platform bør adskille strategi, risikokontrol, broker-integration og observability. Denne separation gør det lettere at teste forretningsregler, begrænse skade fra fejl, udskifte strategier og forklare systemets tilstand under drift. Projektet viser samtidig, at et sådant system har tydelige begrænsninger: Risk Gatewayens state er i den nuværende version in-memory, audit og reconciliation er kun delvist etableret, og live trading kræver yderligere sikkerhed, secrets management og driftsrutiner.

## Indholdsfortegnelse

TODO: Generer automatisk i Word efter sidste redigering.

1. Indledning  
2. Problemformulering  
3. Formål, målgruppe og afgrænsning  
4. Metode og arbejdsproces  
5. Domæneanalyse  
6. Kravspecifikation  
7. Teknologivalg  
8. Arkitektur og systemdesign  
9. Implementering  
10. Test og validering  
11. Drift, observability og fejlfinding  
12. Sikkerhed, risiko og etik  
13. Diskussion  
14. Perspektivering  
15. Konklusion  
16. Litteraturliste  
17. Bilag

## 1. Indledning

Algoritmisk handel handler om at lade software analysere data og udføre handelsbeslutninger efter regler. Det kan være alt fra simple strategier, der køber og sælger ud fra glidende gennemsnit, til avancerede systemer med mange datakilder og risikomodeller. Fælles for dem er, at de bevæger sig i et domæne, hvor fejl i software ikke kun giver en dårlig brugeroplevelse, men potentielt kan få direkte økonomiske konsekvenser.

Det er teknisk muligt at bygge en handelsbot, som forbinder direkte til Interactive Brokers og placerer ordrer. Det er også den mest oplagte løsning, hvis man kun fokuserer på at få en strategi til at handle hurtigt. Problemet er, at denne løsning blander mange ansvar i samme proces: strategien skal både beregne signaler, kende brokerens API, håndtere fejl, styre risiko, logge hændelser og genoprette forbindelse. Når ansvar blandes på den måde, bliver det svært at teste, forklare og begrænse fejl.

AmalieTrader er udviklet som et alternativ til den simple bot. Projektet undersøger, hvordan man kan bygge en lille, men realistisk trading-platform, hvor strategier ikke får direkte adgang til brokerens API. I stedet skal en strategi sende en ordreintention til et centralt risikolag. Først når ordren er valideret, sendes den videre til en central adapter, som ejer forbindelsen til Interactive Brokers. Platformen er dermed designet omkring princippet om separation of concerns: hver komponent har et klart ansvar, og de kritiske beslutningspunkter er tydelige.

Projektets praktiske produkt er en kodebase med flere services, Docker-images og et Helm chart til Kubernetes. De vigtigste services er `strategy-hello`, `risk-gateway`, `ibkr-adapter`, `risk-monitor`, `api` og `dashboard`. Derudover indgår IB Gateway, NATS JetStream og TimescaleDB/PostgreSQL som centrale infrastrukturkomponenter. Systemet er primært afprøvet i paper trading, fordi formålet er at teste det tekniske ordreflow uden at risikere rigtige penge.

Rapporten henvender sig til fagligt kompetente læsere med datamatikerbaggrund. Derfor forklares almindelige programmeringsbegreber kun kort, mens domænespecifikke begreber som Interactive Brokers, paper trading, broker gateway, NATS, Helm og pre-trade risk forklares mere grundigt.

## 2. Problemformulering

Projektets overordnede problemformulering er:

**Hvordan kan der udvikles en Kubernetes-baseret trading-platform, hvor algoritmiske handelsstrategier kan sende ordrer til Interactive Brokers gennem en kontrolleret, observerbar og risikostyret arkitektur?**

Problemformuleringen undersøges gennem følgende underspørgsmål:

1. Hvordan kan ordreflowet designes, så strategier ikke sender ordrer direkte til brokerens API?
2. Hvordan kan pre-trade risikokontrol implementeres som en selvstændig service?
3. Hvordan kan en central adapter isolere integrationen til Interactive Brokers?
4. Hvordan kan NATS anvendes som intern beskedbus mellem services?
5. Hvordan kan systemet deployes og konfigureres reproducerbart med Docker, Kubernetes og Helm?
6. Hvordan kan systemets tilstand synliggøres gennem API, dashboard, metrics og Telegram-alerts?
7. Hvilke begrænsninger har prototypen, og hvad kræver en senere produktionsmodning?

Problemformuleringen er praksisnær, fordi den tager udgangspunkt i en konkret teknisk udfordring: at bygge software, der kan handle mod en broker, uden at lade en strategi alene bære ansvaret for risiko, drift og integration. Den er samtidig relevant for datamatikeruddannelsen, fordi løsningen kræver systemudvikling, programmering, deployment, fejlfinding, dokumentation og teknologivalg på tværs af flere komponenter.

## 3. Formål, målgruppe og afgrænsning

### 3.1 Formål

Formålet med projektet er ikke at udvikle en profitabel handelsstrategi. Formålet er at udvikle den tekniske platform, som strategier kan køre i. Det betyder, at projektets kvalitet ikke vurderes ud fra afkast, men ud fra om arkitekturen kan håndtere ordreflow, risikokontrol, broker-integration og drift på en struktureret måde.

Projektet skal demonstrere, at en handelsstrategi kan generere en ordreintention, at Risk Gateway kan validere ordren, at NATS kan transportere den accepterede ordre, at IBKR-adapteren kan oversætte den til Interactive Brokers, og at systemets tilstand kan observeres gennem risk-monitor, API og dashboard.

### 3.2 Målgruppe

Den primære målgruppe er tekniske brugere, der ønsker at eksperimentere med algoritmisk handel på en mere kontrolleret måde end en enkeltstående bot. Det kan være en privat investor med programmeringserfaring, en studerende, en udvikler eller et lille team, der vil teste strategier i paper trading.

Den sekundære målgruppe er en teknisk censor, vejleder eller medstuderende, som skal kunne forstå, hvorfor systemet er bygget som en platform. Rapporten skal derfor gøre det tydeligt, hvad hver service gør, hvordan de kommunikerer, og hvilke risici arkitekturen forsøger at reducere.

### 3.3 Afgrænsning

Projektet afgrænses til en prototype til paper trading og teknisk validering. Paper trading betyder, at ordrer sendes mod en simuleret konto hos Interactive Brokers, hvor man kan teste uden at bruge rigtige penge. Arkitekturen indeholder konfiguration til både paper og live mode, men rapporten behandler ikke systemet som produktionsklart til live trading.

Følgende indgår i projektet:

- en eksempelstrategi baseret på simple moving averages,
- en Risk Gateway med pre-trade checks,
- NATS som beskedbus,
- en central IBKR-adapter baseret på `ib_insync`,
- IB Gateway som bro til Interactive Brokers,
- en risk-monitor med circuit breaker og Telegram-alerts,
- et read-only API og dashboard,
- Docker-packaging og Helm chart til Kubernetes,
- en databasestruktur til fills, PnL, positions-snapshots, ordre-events og market data.

Følgende er ikke fuldt implementeret i v0-prototypen:

- avanceret backtesting af strategier,
- produktionsklar live trading,
- fuld broker-reconciliation med automatisk drift recovery,
- fuld persistent auditlog fra alle eventtyper,
- ekstern secret manager og komplet adgangskontrol,
- multi-tenant brugerhåndtering,
- en garanti for strategi-specifik positionsejerskab hos Interactive Brokers.

Afgrænsningen er bevidst. Trading-domænet er stort, og en realistisk platform kan hurtigt omfatte markedsdata, backtesting, portfoliooptimering, order management, compliance, brugeradministration og dataanalyse. Dette projekt fokuserer på den centrale kæde fra strategi til broker og tilbage til overvågning.

## 4. Metode og arbejdsproces

Projektet er gennemført iterativt med fokus på at få et end-to-end flow til at fungere tidligt. I stedet for at færdiggøre hver komponent isoleret blev en vertikal kæde prioriteret:

```text
Strategi -> HTTP POST /orders -> Risk Gateway -> NATS -> ibkr-adapter -> IB Gateway -> Interactive Brokers
```

Denne arbejdsform passer til projektets tekniske risiko. Den største usikkerhed lå ikke i, om en enkelt FastAPI-service kunne bygges, men i om mange services kunne arbejde sammen: strategi, gateway, beskedbus, adapter, broker, monitorering og dashboard. Ved tidligt at bygge en sammenhængende kæde blev det muligt at opdage integrationsproblemer tidligere.

Arbejdet kan beskrives i fem faser.

Første fase var domæneanalyse. Her blev Interactive Brokers' gatewaymodel, paper trading, client IDs, account-level positioner og brokerforbindelser undersøgt. En vigtig indsigt var, at Interactive Brokers ikke isolerer positioner pr. strategi. Hvis to strategier handler samme symbol på samme konto, ser brokeren kun den samlede position. Derfor kan platformen ikke påstå at have broker-garanteret strategi-isolation. Strategi-ejerskab må håndteres som lokal metadata, for eksempel via `orderRef`, events og intern state.

Anden fase var arkitekturdesign. Her blev det besluttet, at strategier ikke skulle tale direkte med IB Gateway. En central adapter skulle eje brokerforbindelsen, og Risk Gateway skulle være obligatorisk før alle ordrer. NATS blev valgt som beskedbus for at reducere koblingen mellem de enkelte services.

Tredje fase var implementering af services. Python blev brugt til backend-services, fordi projektet har meget integration, datavalidering og asynkron I/O. FastAPI blev brugt i Risk Gateway og API, mens adapteren bruger `ib_insync` til Interactive Brokers.

Fjerde fase var containerisering og deployment. Hver service fik Docker-packaging, og Helm-chartet blev udvidet, så hele systemet kan installeres som en samlet release. Dette gør projektet mere reproducerbart end en lokal samling scripts.

Femte fase var test og driftsvalidering. Unit tests blev brugt til risikoregler og strategi-adfærd, mens end-to-end afprøvning blev brugt til at validere, at dashboard, API, adapter heartbeat og paper-konto kunne ses i et kørende miljø. Under denne fase blev der blandt andet observeret Telegram-beskeder om adapter heartbeat timeout, hvilket viste værdien af at have driftsalerts, men også afslørede behovet for tydelig forklaring af heartbeat-mekanismen.

Metoden er dermed ikke en ren teoretisk analyse. Den er en praksisnær udviklingsproces, hvor arkitekturvalg løbende er blevet justeret ud fra kode, test og driftserfaringer.

## 5. Domæneanalyse

### 5.1 Algoritmisk handel

Algoritmisk handel betyder, at regler i software afgør, hvornår en ordre skal placeres. En regel kan være simpel, for eksempel at købe når et kort glidende gennemsnit ligger over et langt glidende gennemsnit. Den kan også være avanceret og bruge statistiske modeller, porteføljeteori eller maskinlæring. I dette projekt er strategien bevidst simpel, fordi platformens infrastruktur er det centrale.

Den tekniske risiko ved algoritmisk handel opstår, fordi systemet kan handle hurtigere og mere gentaget end et menneske. En bug i en loop, en forkert quantity, en reconnect-fejl eller en misforstået position kan føre til mange ordrer på kort tid. Derfor er det vigtigt at indbygge kontrolpunkter, rate limiting, idempotency og observability.

### 5.2 Interactive Brokers og IB Gateway

Interactive Brokers er en broker, der tilbyder API-adgang via blandt andet Trader Workstation og IB Gateway. IB Gateway er en separat applikation, som en klient kan forbinde til. I dette projekt kører IB Gateway som en container i Kubernetes, og `ibkr-adapter` forbinder til den via host, port og client ID.

IBKR-domænet har nogle begrænsninger, som påvirker arkitekturen:

- Positioner ligger på kontoniveau, ikke på strateginiveau.
- Hver API-klient skal bruge et `clientId`.
- Gateway-sessionen kan afbrydes og skal kunne genforbindes.
- Paper trading og live trading skal adskilles tydeligt.
- Brokerens callbacks skal behandles som den vigtige sandhed om fills og positioner.

Disse begrænsninger gør det fornuftigt at samle brokerkommunikationen ét sted. Hvis hver strategi selv forbinder til IB Gateway, skal hver strategi håndtere reconnects, order IDs, callbacks, PnL og fejl. Ved at bruge en central adapter bliver brokerintegrationen et fælles ansvar i platformen.

### 5.3 Paper trading og live trading

Paper trading er et testmiljø, hvor ordrer simuleres på en paper-konto. Det gør det muligt at validere ordreflow, API-kald og risikologik uden at risikere rigtige penge. Paper trading er dog ikke det samme som produktionsklarhed. En ordre, der fungerer i paper mode, siger ikke nødvendigvis alt om slippage, markedsforhold, likviditet, latency eller psykologiske risici ved live trading.

I AmalieTrader bruges paper trading som realistisk teknisk testmiljø. Systemet kan forbinde til en IBKR paper-konto, vise account status i dashboardet og sende ordrer gennem samme softwarekæde, som senere kunne bruges i live mode. Det er en styrke for projektet, fordi det gør testen mere realistisk end en ren mock. Samtidig skal rapporten være ærlig om, at live trading kræver yderligere sikkerhed og driftsmodning.

### 5.4 Flere strategier på én broker-konto

Et centralt mål er, at flere strategier på sigt kan køre i samme platform. Det giver tekniske fordele: man kan deploye hver strategi separat, give dem egne limits og overvåge dem centralt. Udfordringen er, at Interactive Brokers ikke har et indbygget begreb om "strategi A's position". Hvis strategi A køber 10 aktier, og strategi B sælger 4 af samme symbol, ser brokeren kun nettostillingen på kontoen.

Derfor skal strategi-ejerskab håndteres internt i platformen. Ordrebeskeder indeholder felter som `strategy`, `client_id` og `idempotency_key`. IBKR-adapteren bruger `orderRef` til at sende idempotency key videre til IBKR-ordren. Det kan hjælpe med sporing, men det er ikke det samme som en broker-garanteret adskillelse. Denne begrænsning er vigtig at kunne forsvare til eksamen, fordi den viser forståelse for forskellen mellem lokal systemstate og brokerens faktiske account state.

### 5.5 Risiko i automatiseret handel

De vigtigste risici i projektets domæne er:

- en strategi sender for store ordrer,
- en strategi sender duplicate orders,
- en strategi handler et symbol, der bør være blokeret,
- en limit price ligger langt fra markedsprisen,
- systemet mister forbindelsen til IBKR,
- positioner eller PnL bliver forældede,
- flere services har forskellig opfattelse af systemets state,
- en fejl i deployment skaber flere instanser af en komponent, der kun bør findes én af.

AmalieTrader reducerer nogle af disse risici med Risk Gateway, idempotency, heartbeat, circuit breaker, health endpoints, metrics og Helm-konfiguration. Andre risici er kun delvist reduceret i prototypen og beskrives i diskussionen.

## 6. Kravspecifikation

Kravene er opdelt i funktionelle krav, ikke-funktionelle krav og afgrænsede v0-begrænsninger. Kravene tager udgangspunkt i problemformuleringen og den faktiske kodebase.

### 6.1 Funktionelle krav

| ID | Krav | Status |
|---|---|---|
| F1 | Systemet skal kunne køre mindst én handelsstrategi som selvstændig service. | Implementeret med `strategy-hello`. |
| F2 | Strategier skal sende ordreintentioner til Risk Gateway via HTTP. | Implementeret via `POST /orders`. |
| F3 | Risk Gateway skal validere ordrer før de sendes videre. | Implementeret med check pipeline. |
| F4 | Accepterede ordrer skal publiceres på en intern beskedbus. | Implementeret med NATS subject `orders.<strategy>.<symbol>`. |
| F5 | IBKR-adapteren skal lytte på ordrebeskeder og placere ordrer gennem IB Gateway. | Implementeret i `nats_bridge.py` og `gateway.py`. |
| F6 | Adapteren skal publicere broker-events som fills, positioner, PnL og heartbeat. | Implementeret for centrale eventtyper. |
| F7 | Risk-monitor skal kunne evaluere account risk og sende alerts. | Implementeret med circuit breaker og Telegram integration. |
| F8 | Dashboardet skal vise status, PnL, positioner og fills. | Implementeret som read-only dashboard. |
| F9 | Systemet skal kunne konfigureres til paper/live mode. | Understøttet i Helm values, men projektets validering er paper mode. |
| F10 | Systemet skal kunne deployes med Helm. | Implementeret i chartet `helm/ibkrtrader`. |

### 6.2 Ikke-funktionelle krav

| Krav | Begrundelse | Løsning i projektet |
|---|---|---|
| Modularitet | Strategier og infrastruktur skal kunne udvikles separat. | Microservices med separate mapper og images. |
| Reproducerbarhed | Miljøet skal kunne genskabes uden manuel opsætning af alle services. | Docker og Helm chart. |
| Observerbarhed | Driftstilstand skal kunne vurderes uden at læse kode. | Health endpoints, metrics, dashboard og Telegram-alerts. |
| Testbarhed | Risikoregler skal kunne testes uden brokerforbindelse. | Unit tests for checks, modeller og circuit breaker. |
| Fail-safe adfærd | Kritiske fejl bør stoppe eller begrænse handel. | Risk Gateway, circuit breaker og kill switch design. |
| Konfigurerbarhed | Paper/live, limits og strategier skal kunne ændres uden kodeændring. | Pydantic settings og Helm values. |
| Sporbarhed | Ordreflow og broker-events bør kunne følges. | NATS subjects, strukturerede modeller og database schema. |

### 6.3 MoSCoW-prioritering

| Prioritet | Indhold |
|---|---|
| Must have | Strategi -> Risk Gateway -> NATS -> adapter -> IB Gateway flow, pre-trade checks, paper mode, health endpoints, Helm deployment. |
| Should have | Risk-monitor, Telegram-alerts, dashboard, database schema, metrics, unit tests for centrale regler. |
| Could have | Flere strategier, historiske grafer, bedre reconciliation, mere komplet audit persistence. |
| Won't have i v0 | Produktionsklar live trading, avanceret backtesting, multi-user auth, automatisk broker recovery for alle drift-scenarier. |

### 6.4 Acceptkriterier

Projektets centrale acceptkriterier er:

1. En strategi kan sende en ordreintention til `POST /orders`.
2. Risk Gateway kan afvise en ordre med en struktureret årsag.
3. Risk Gateway kan acceptere en ordre og publicere den på NATS.
4. IBKR-adapteren kan modtage ordrebeskeden fra `orders.>`.
5. Adapteren sender kun ordren til IBKR, hvis gatewayforbindelsen er aktiv.
6. Adapteren publicerer heartbeat, så systemet kan overvåge liveness.
7. Risk-monitor kan sende alert ved heartbeat timeout.
8. Dashboardet kan vise status for account, adapter og systemets read-only data.
9. Helm chartet kan beskrive den samlede deploymenttopologi.
10. Centrale risikoregler kan testes med automatiserede tests.

## 7. Teknologivalg

### 7.1 Python

Python er valgt til backend-services, fordi projektet har meget integration, datavalidering og asynkron kommunikation. Python har stærke biblioteker til HTTP-services, datamodeller, test og brokerintegration. `ib_insync` er desuden et udbredt Python-bibliotek til Interactive Brokers API, hvilket gør Python til et naturligt valg for adapteren.

En ulempe ved Python er, at runtime-fejl kan opstå, hvis typer og integrationer ikke testes ordentligt. Projektet reducerer dette ved at bruge Pydantic-modeller, pytest og klare servicegrænser.

### 7.2 FastAPI og Pydantic

FastAPI bruges i `risk-gateway` og `api`. Det passer godt til projektet, fordi det bygger på Pydantic-validering og asynkron I/O. Ordreinput kan beskrives som modeller, og ugyldige requests kan afvises tidligt. Det er især relevant i Risk Gateway, hvor validering og tydelige fejlbeskeder er en del af sikkerheden.

Pydantic bruges også til settings. Det betyder, at miljøvariabler fra Kubernetes og Helm kan mappes til typed configuration i services. Det gør systemet lettere at deploye og fejlfinde, fordi konfiguration er samlet og valideret.

### 7.3 NATS JetStream

NATS er valgt som beskedbus mellem services. I stedet for at Risk Gateway kalder adapteren direkte via HTTP, publiceres accepterede ordrer på et subject. Adapteren abonnerer på `orders.>`. Dette giver lav kobling mellem services og gør det muligt for andre komponenter at lytte med på events.

JetStream giver mulighed for mere holdbar eventhåndtering, selvom prototypen også har fallback til core NATS i udviklingsmiljøer, hvis en stream ikke findes. Det er pragmatisk i en v0-version, fordi lokal udvikling ikke skal gå i stå på fuld stream-konfiguration.

### 7.4 Docker, Kubernetes og Helm

Docker bruges til at pakke hver service som et image. Kubernetes bruges som driftsmiljø, fordi systemet består af flere services, som skal startes, forbindes, health-checkes og konfigureres. Helm bruges til at beskrive den samlede installation.

Helm-chartet er et centralt produkt i projektet, fordi det gør arkitekturen konkret. Det beskriver IB Gateway, adapter, strategier, Risk Gateway, risk-monitor, API, dashboard, NATS og database. Det giver også et sted at konfigurere paper/live mode, risk limits, client IDs og image references.

En vigtig detalje er, at adapteren kun bør køre med én replica, fordi den ejer et bestemt IBKR client ID og en brokerforbindelse. Strategier genereres ud fra `values.yaml`, og client IDs valideres for at undgå dubletter.

### 7.5 TimescaleDB/PostgreSQL

TimescaleDB bygger oven på PostgreSQL og er valgt til tidsseriedata som fills, PnL og position snapshots. Projektets migrationsfil opretter blandt andet tabellerne `fills`, `pnl_ticks`, `positions_snapshot`, `order_events` og `marketdata_bars`. Det passer til trading-domænet, hvor mange data er tidsstemplede events.

I v0-prototypen er databaseskemaet en vigtig del af designet, men alle eventveje er ikke nødvendigvis fuldt persistente endnu. Derfor beskrives audit persistence som delvist etableret og som et vigtigt perspektiv for videreudvikling.

### 7.6 Next.js, SWR og Recharts

Dashboardet er bygget med Next.js, React, SWR, Tailwind og Recharts. Det er et read-only dashboard, der viser systemets status, PnL, positioner, fills og historik. SWR bruges til polling, så dashboardet opdaterer data løbende uden at brugeren manuelt skal genindlæse siden.

Dashboardet er ikke et kontrolpanel til at placere manuelle ordrer. Det er et bevidst valg i prototypen, fordi skriveadgang fra UI ville kræve ekstra sikkerhed, brugerrettigheder og audit.

### 7.7 Telegram-alerts

Telegram bruges som alert-kanal i risk-monitor. Det er en enkel måde at sende beskeder om vigtige hændelser på, for eksempel heartbeat timeout eller halt. Telegram er ikke en erstatning for fuld observability, men det giver en konkret operatørbesked, når noget kræver opmærksomhed.

I projektet betyder en "adapter heartbeat timeout", at risk-monitor ikke har modtaget en liveness-besked fra adapteren inden for den konfigurerede tid. Det betyder ikke nødvendigvis, at en ordre er fejlet, men det betyder, at platformen ikke længere har frisk bekræftelse på adapterens tilstand.

## 8. Arkitektur og systemdesign

### 8.1 Overordnet arkitektur

AmalieTrader er bygget som en event-drevet microservice-arkitektur. Det centrale ordreflow er:

```text
strategy-hello
  -> HTTP POST /orders
  -> risk-gateway
  -> NATS orders.<strategy>.<symbol>
  -> ibkr-adapter
  -> IB Gateway
  -> Interactive Brokers
```

Broker-events bevæger sig den modsatte vej:

```text
Interactive Brokers
  -> IB Gateway
  -> ibkr-adapter
  -> NATS fills/positions/pnl/risk events
  -> risk-monitor / api / dashboard
```

Designet har et klart princip: Strategier genererer intent, Risk Gateway beslutter om intent må fortsætte, NATS transporterer accepterede events, adapteren ejer broker-I/O, og observability-komponenter læser state.

### 8.2 Separation of concerns

Separation of concerns er en af de vigtigste arkitekturbeslutninger. Hver service har et afgrænset ansvar:

| Komponent | Ansvar |
|---|---|
| `strategy-hello` | Genererer handelssignaler og ordreintentioner. |
| `risk-gateway` | Validerer ordrer synkront før de når brokerlaget. |
| NATS | Transporterer ordre- og broker-events mellem services. |
| `ibkr-adapter` | Ejer forbindelsen til IB Gateway og oversætter mellem intern model og IBKR API. |
| IB Gateway | Brokerens gateway-applikation mod Interactive Brokers. |
| `risk-monitor` | Overvåger account risk og driftstilstand out-of-band. |
| `api` | Eksponerer read-only data til dashboardet. |
| `dashboard` | Viser status, PnL, positioner og fills. |
| TimescaleDB/PostgreSQL | Lagrer historiske trading- og tidsseriedata. |

Denne opdeling gør systemet lettere at teste. Risk Gatewayens checks kan testes uden IBKR. Strategiens signaler kan testes uden broker. Adapterens modeller kan testes uden dashboard. Det gør også systemet lettere at forklare, fordi hver service har en tydelig rolle.

### 8.3 Hvorfor Risk Gateway findes

Risk Gateway er systemets synkrone pre-trade kontrolpunkt. Den står i ordrevejen og modtager alle ordreintentioner fra strategier. Hvis en ordre bryder en regel, returnerer Risk Gateway en afvisning og publicerer ikke ordren på NATS.

De implementerede checks omfatter:

- global halt flag,
- restricted symbols,
- fat-finger kontrol for limit-priser,
- max order notional pr. strategi,
- max daily loss pr. strategi,
- max position pr. strategi,
- rate limit pr. strategi,
- global rate limit,
- idempotency key for duplicate detection.

Risk Gatewayen afgør ikke, om en strategi er profitabel. Den afgør kun, om en konkret ordre er tilladt inden for systemets regler. Det svarer til en teknisk sikkerhedsbarriere mellem handelslogik og broker.

En vigtig begrænsning er, at Risk Gatewayens state i v0 holdes in-memory. Det gælder blandt andet idempotency-cache, rate limit-vinduer, positioner og halt-state. Det er acceptabelt for en prototype og en enkelt replica, men det er ikke tilstrækkeligt til en robust multi-replica produktion. Hvis to Risk Gateway pods kører uden delt state, kan de have forskellig opfattelse af duplicate orders og rate limits. En videreudvikling bør derfor flytte denne state til Redis, database eller en anden delt state store.

### 8.4 Hvorfor en central adapter findes

IBKR-adapteren er et centralt adapterlag mellem platformens interne events og Interactive Brokers. Den abonnerer på `orders.>` og kalder `place_order()` på gatewaylaget, når den modtager en valid ordrekommando.

Adapterens ansvar er at:

- forbinde til IB Gateway,
- genforbinde ved fejl,
- placere ordrer,
- opbygge IBKR `Contract` og `Order` objekter,
- modtage fills, PnL og positions-callbacks,
- publicere broker-events på NATS,
- sende heartbeat-events.

At adapteren er central betyder, at strategier ikke skal kende IBKR API'et. Hvis IBKR-integration ændres, er ændringen isoleret til adapteren. Det gør også systemet mere sikkert, fordi brokeradgang kan begrænses til én service.

### 8.5 Eventbus og subjects

NATS bruges som intern kommunikationskanal. Projektet bruger subjects, der afspejler eventtypen:

| Subject | Formål |
|---|---|
| `orders.<strategy>.<symbol>` | Accepterede ordrekommandoer fra Risk Gateway. |
| `orders.>` | Adapterens wildcard subscription på alle ordrekommandoer. |
| `fills.<account>.<symbol>` | Brokerbekræftede executions. |
| `positions.<account>.<symbol>` | Positionssnapshots. |
| `pnl.<account>` | PnL snapshots. |
| `risk.adapter.heartbeat` | Adapterens liveness-signal. |
| `risk.adapter.disconnected` | Adapter disconnect event. |
| `risk.halt` | Circuit breaker halt-state. |
| `marketdata.realtime.<symbol>` | Markedsdata til strategier. |

Fordelen ved eventbus er, at flere services kan reagere på samme event uden at kende hinanden direkte. Risk-monitor kan lytte på broker-events, API kan opdatere cache, og fremtidige audit-consumers kan gemme events. Ulempen er, at systemet bliver mere distribueret, og fejl kan opstå på tværs af asynkrone led. Derfor er logging, metrics og klare eventmodeller vigtige.

### 8.6 Risk-monitor og circuit breaker

Risk-monitoren er et out-of-band risikolag. Den står ikke i ordrevejen, men overvåger kontoens tilstand løbende. Den lytter til NATS-events om heartbeat, PnL, fills, positioner og risk. En circuit breaker evaluerer state mod konfigurerede grænser.

Circuit breakerens centrale regler er:

- hvis daily PnL falder under max daily loss, skal systemet halte,
- hvis drawdown overstiger grænsen, skal systemet halte,
- hvis gross exposure overstiger grænsen, skal systemet halte,
- hvis adapter heartbeat udebliver, sendes alert, men strategier stoppes ikke automatisk i v0.

Denne forskel mellem halt og alert-only er vigtig. Et heartbeat timeout betyder, at monitoren mangler frisk livstegn fra adapteren. Det kan skyldes en reel forbindelsefejl, men det kan også skyldes midlertidige reconnects eller deployment. Derfor er heartbeat timeout i prototypen en alarm, ikke automatisk nedlukning.

Risk-monitoren bruger leader election via Kubernetes Lease, så kun én aktiv leder udfører handlinger, selv hvis der kører flere replicas. Det reducerer risikoen for dobbelte alerts eller flere samtidige kill switch-handlinger.

### 8.7 API og dashboard

API-servicen er read-only og bruges af dashboardet. Den eksponerer endpoints som `/status`, `/positions`, `/pnl`, `/pnl/history`, `/fills` og `/orders`. API'et bruger en in-memory cache til aktuelle data og kan falde tilbage til database for historik.

Dashboardet viser operationel information: account status, om adapteren er connected, om systemet er halted, PnL, positioner, fills og historiske grafer. Det er bevidst ikke et trade execution UI. I et trading-system bør skriveadgang fra frontend først indføres, når authentication, authorization, audit og manual override-regler er designet.

### 8.8 Deployment-arkitektur

Helm-chartet beskriver hele systemet som en Kubernetes-release. Det deployer blandt andet:

- IB Gateway StatefulSet og Service,
- IBKR-adapter Deployment,
- strategy Deployment pr. strategi i `values.yaml`,
- Risk Gateway Deployment,
- risk-monitor Deployment og RBAC,
- API Deployment,
- dashboard Deployment,
- NATS dependency chart,
- CloudNativePG/Timescale ressourcer,
- optional ServiceMonitor ressourcer.

IB Gateway er en StatefulSet, fordi gatewayen har session og lokal konfiguration. Adapteren er én replica, fordi den ejer én brokerforbindelse og ét client ID. Strategier kører som separate Deployments, så en strategi kan opdateres uden at røre de andre.

## 9. Implementering

### 9.1 Repository-struktur

Repositoryet er organiseret omkring services og Helm-chartet:

```text
.
|-- build-and-push.ps1
|-- helm/
|   `-- ibkrtrader/
|-- services/
|   |-- api/
|   |-- dashboard/
|   |-- ibkr-adapter/
|   |-- risk-gateway/
|   |-- risk-monitor/
|   `-- strategy-hello/
```

Denne struktur gør det tydeligt, at projektet ikke er én applikation, men en samlet platform. Hver service kan have egne dependencies, tests og Dockerfile. `build-and-push.ps1` bygger og pusher images til GitHub Container Registry.

### 9.2 Strategy service

`strategy-hello` er eksempelstrategien. Den bygger på en `BaseStrategy`, som håndterer NATS-forbindelse, health endpoints, metrics og HTTP-kald til Risk Gateway. Strategiens egen logik ligger i `on_bar()`.

Strategien vedligeholder en rullende buffer af close-priser pr. symbol. Den beregner et hurtigt og et langsomt glidende gennemsnit. Hvis fast MA ligger over slow MA, og strategien ikke allerede er long, forsøger den at købe. Hvis fast MA ligger under slow MA, og strategien er long, forsøger den at sælge.

Koden beskriver dette som crossover-logik, men den nuværende implementation sammenligner primært den aktuelle fast MA og slow MA, ikke et fuldt tidligere-bar kryds. Det er en acceptabel forenkling i en platformprototype, men det bør nævnes som begrænsning, hvis strategien senere vurderes som handelsstrategi. Strategien er først og fremmest en test af platformens ordreflow.

Når strategien vil handle, sender den et JSON-payload til Risk Gateway. Payloadet indeholder blandt andet `strategy`, `symbol`, `side`, `quantity`, `order_type`, `client_id` og `idempotency_key`. Idempotency key genereres som UUID, så duplicate detection kan ske i Risk Gateway.

### 9.3 Risk Gateway

Risk Gatewayen er implementeret som en FastAPI-service. Den har ruten `POST /orders`, som modtager et `OrderRequest`. Først køres `engine.check(req)`. Hvis et check fejler, returneres HTTP 422 med `OrderRejected` og en årsag. Hvis ordren accepteres, publiceres den på NATS subject `orders.<strategy>.<symbol>`.

Denne implementation har tre styrker.

For det første er regellogikken isoleret i `CheckEngine`. Det gør checks testbare uden HTTP-server og uden NATS. For det andet er rejection reasons klassificeret til Prometheus metrics, så man kan se, hvorfor ordrer afvises. For det tredje er success path og rejection path tydeligt adskilt: en rejected ordre publiceres ikke videre.

Risk Gatewayens vigtigste tekniske kompromis er in-memory state. Det gør prototypen enkel, men det betyder, at flere replicas kan give inkonsistent risk-state. I en produktionsversion bør state externaliseres, og gatewayen bør sandsynligvis fail-closed, hvis den ikke kan læse delt state.

### 9.4 IBKR-adapter

IBKR-adapteren består af et gatewaylag og en NATS bridge. `NATSBridge` forbinder til NATS, abonnerer på `orders.>` og validerer indkommende beskeder som `OrderCommand`. Hvis adapterens gateway ikke er connected, dropper den ordren og øger en rejected metric med reason `not_connected`. Hvis gatewayen er connected, kaldes `place_order()`.

`IBKRGateway` wrapper `ib_insync`. Den forbinder til IB Gateway med host, port og client ID. Den har reconnect-logik og en heartbeat loop, som sender et `risk.adapter.heartbeat` event hvert 15. sekund, mens forbindelsen er aktiv. Den håndterer også callbacks for executions, PnL og positioner og publicerer dem tilbage på NATS via en callback.

Når en ordre placeres, bygger adapteren et IBKR `Contract` og et `Order`. `orderRef` sættes til idempotency key, så ordren kan spores tilbage til platformens interne ordre. Det er nyttigt for audit og fejlfinding, selvom det ikke giver broker-garanteret strategi-isolation.

### 9.5 Risk-monitor

Risk-monitoren samler account state ud fra NATS-events. Den har en reconcile loop, som med faste intervaller evaluerer state via `CircuitBreaker`. Hvis daily loss, drawdown eller gross exposure bryder en grænse, sættes `state.halted`, der sendes Telegram-alert, og kill switch kan skalere strategi-deployments ned til nul. Hvis heartbeat mangler, sendes en alert-only besked.

Risk-monitoren er designet til at kunne køre med flere replicas, men kun én leader handler. Det håndteres med Kubernetes Lease. Denne løsning er relevant, fordi risk-monitor er en kontrolkomponent: hvis to replicas samtidigt udførte kill switch-handlinger, kunne det give støj og uforudsigelig drift.

### 9.6 API og dashboard

API'et samler data til dashboardet. Det har health- og readiness-endpoints og read-only routes til status, positioner, PnL, PnL-historik, fills og orders. Dashboardet henter data via en intern API wrapper og opdaterer med SWR. Det gør dashboardet enkelt og robust nok til v0.

Dashboardet kan bruges til at se, om adapteren er connected, om systemet er halted, hvilken account der er aktiv, samt om der findes fills, positioner eller PnL-data. Hvis dashboardet viser tomme tabeller, betyder det ikke nødvendigvis, at systemet er nede. Det kan også betyde, at der endnu ikke er fills eller åbne positioner på paper-kontoen.

### 9.7 Database

Migrationsfilen opretter tabeller til trading-relaterede tidsserier:

- `fills` til executions,
- `pnl_ticks` til PnL snapshots,
- `positions_snapshot` til positionsdata,
- `order_events` til ordre-audit,
- `marketdata_bars` til OHLCV-data.

Derudover oprettes en continuous aggregate `pnl_1min`, som kan bruges til mere chart-venlig PnL-historik. Databasedesignet viser, hvordan platformen kan bevæge sig mod mere permanent audit og historik. I v0 skal det dog beskrives som et fundament, ikke som fuldt gennemført audit persistence for alle eventtyper.

### 9.8 Helm chart og konfiguration

Helm chartet gør produktet deploybart. `values.yaml` indeholder standardkonfiguration, mens `values.paper.yaml` og `values.live.yaml` bruges til miljøspecifikke overrides. Vigtige konfigurationsfelter er blandt andet:

- `ibkr.mode`,
- `ibkrAdapter.clientId`,
- strategi-navne og `clientId`,
- risk limits,
- NATS URL,
- IB Gateway host/port,
- Telegram settings,
- image registry og tags.

Konfigurationsmodellen er vigtig, fordi trading-systemer ofte skal kunne ændre limits og miljø uden kodeændringer. Samtidig giver Helm en måde at dokumentere arkitekturen som kode.

## 10. Test og validering

### 10.1 Teststrategi

Teststrategien er todelt. Unit tests bruges til logik, der kan testes isoleret, mens end-to-end validering bruges til at kontrollere, at den distribuerede kæde fungerer i et kørende miljø.

Unit tests er særligt vigtige for risk-regler. En brokerforbindelse er langsom, ekstern og svær at styre i tests, men Risk Gatewayens checks kan testes deterministisk. Derfor ligger en stor del af testværdien i at sikre, at farlige ordrer afvises, før de når adapteren.

### 10.2 Unit tests

Projektet indeholder pytest-tests for flere services:

| Service | Testfokus |
|---|---|
| `risk-gateway` | restricted symbols, fat-finger, notional, daily loss, idempotency og rate limits. |
| `ibkr-adapter` | modeller og NATS bridge-adfærd. |
| `risk-monitor` | account state og circuit breaker. |
| `strategy-hello` | strategi-adfærd og order submission. |

Der er tidligere kørt tests for `strategy-hello`, hvor resultatet var 6 passing tests. Det dokumenterer ikke hele systemet, men det viser, at strategi-servicens centrale adfærd kan testes uden broker.

### 10.3 Test af en bestemt handelsstrategi

En bestemt strategi kan testes på flere niveauer.

Først kan signal-logikken testes isoleret. For en moving average-strategi kan man sende en kontrolleret serie af bar-data ind i `on_bar()` og verificere, om strategien kalder `buy()` eller `sell()` på det rigtige tidspunkt. Det kræver ikke NATS, Risk Gateway eller IBKR.

Dernæst kan order submission testes med en mock af Risk Gateway. Her testes det, at strategien sender korrekt JSON: symbol, side, quantity, order type, client ID og idempotency key. Denne test sikrer, at strategien overholder platformens kontrakt.

Tredje niveau er integrationstest mod Risk Gateway. Her kan man starte Risk Gateway med testkonfiguration og sende rigtige HTTP-requests til `/orders`. Man kan teste både accepterede og afviste ordrer.

Fjerde niveau er paper-trading validering. Her kører hele kæden mod IBKR paper account. Det er den mest realistiske test, men også den mest skrøbelige, fordi den afhænger af broker-session, netværk, market hours og IB Gateway.

### 10.4 Scenariebaserede tests

Følgende scenarier er relevante for projektet:

| Scenarie | Forventet resultat |
|---|---|
| Ordre med restricted symbol | Risk Gateway returnerer 422 og publicerer ikke til NATS. |
| Limit price mere end 20 procent fra referencepris | Risk Gateway afviser med fat-finger reason. |
| Duplicate idempotency key | Risk Gateway afviser anden ordre. |
| Adapter ikke connected | NATS bridge modtager ordre, men dropper den med `not_connected`. |
| Adapter heartbeat stopper | Risk-monitor sender Telegram heartbeat timeout alert. |
| Daily loss under grænse | Circuit breaker halter systemet og kan trippe kill switch. |
| Dashboard uden fills | Dashboard viser status, men tomme tabeller for fills/positioner. |

Disse scenarier er vigtige, fordi de tester sikkerhedsadfærd, ikke kun success path. I et trading-system er det mindst lige så vigtigt at vide, hvornår systemet ikke handler.

### 10.5 End-to-end validering mod IBKR paper

Der er arbejdet med at teste kæden mod en IBKR paper-konto. Dashboardet kunne vise account `DUQ568769`, at adapteren var connected, at systemet ikke var halted, og at PnL, positioner, fills og orders var tomme. Det er et realistisk resultat, hvis der ikke er åbne positioner eller udførte handler.

Der blev også observeret Telegram-alert om `ADAPTER HEARTBEAT TIMEOUT`, hvor risk-monitor rapporterede, at der ikke var modtaget heartbeat i en periode. Adapterens logs viste senere IBKR disconnect/reconnect-relaterede events. Dette var en nyttig driftsobservation, fordi den viste, at monitoren faktisk reagerer på manglende liveness-signaler.

En fuld paper-buy test kræver, at IB Gateway er logget ind, at adapteren er connected, at Risk Gateway er ready, at NATS fungerer, og at den valgte ordre er acceptabel i paper-kontoen. Det er ikke nok, at strategien kører. Hele kæden skal være klar.

### 10.6 Validering af problemformuleringen

Problemformuleringen spørger, hvordan man kan bygge en kontrolleret, observerbar og risikostyret arkitektur. Projektet validerer dette ved at vise, at ordreflowet ikke går direkte fra strategi til broker, men gennem Risk Gateway, NATS og adapter. Det viser også, at driftstilstand kan observeres gennem heartbeat, Telegram-alerts, metrics, API og dashboard.

Valideringen er dog ikke komplet produktionsvalidering. Prototypen demonstrerer arkitektur og centrale sikkerhedsmekanismer, men ikke alle krav til live trading, compliance og drift. Denne ærlighed er vigtig, fordi den viser forskellen mellem et hovedopgaveprodukt og et finansielt produktionssystem.

## 11. Drift, observability og fejlfinding

### 11.1 Health endpoints og metrics

Flere services eksponerer health endpoints som `/healthz` og `/readyz`. Det gør Kubernetes i stand til at vurdere, om en service lever og er klar. Risk Gatewayens readiness afhænger eksempelvis af NATS-forbindelsen. Hvis NATS ikke er connected, bør Risk Gateway ikke anses som klar til at modtage ordrer.

Prometheus metrics bruges til at tælle accepterede og afviste ordrer, latency, adapter connection state, fills, PnL, risk-monitor state og alerts. Metrics er vigtige, fordi logs alene ikke giver et hurtigt overblik over systemets tilstand.

### 11.2 Heartbeat

Heartbeat er en periodisk besked fra adapteren til resten af systemet. I AmalieTrader sender adapteren et `risk.adapter.heartbeat` event hvert 15. sekund, når forbindelsen til IB Gateway er aktiv. Risk-monitor gemmer tidspunktet for seneste heartbeat.

Hvis der går længere tid end `HEARTBEAT_TIMEOUT_S`, udløser circuit breaker et alert-only resultat. Risk-monitor sender derefter en Telegram-besked om heartbeat timeout. Pointen er, at monitoren ikke kun skal vide, om podden kører, men om adapteren faktisk giver livstegn fra brokerforbindelsen.

Heartbeat svarer til et teknisk "jeg lever og er connected" signal. Det er ikke en garanti for, at alle fremtidige ordrer kan placeres, men det er en indikator på, at adapteren for nylig havde en aktiv gatewaytilstand.

### 11.3 Telegram-beskeder

I projektet er det meningen, at Telegram-beskeder sendes ved væsentlige risk- eller driftsbegivenheder. De vigtigste er:

- heartbeat timeout fra adapteren,
- halt på grund af daily loss,
- halt på grund af drawdown,
- halt på grund af gross exposure,
- eventuelle kill switch-handlinger.

Det er ikke meningen, at Telegram nødvendigvis sender en besked for hver almindelig ordre eller hvert dashboard-refresh. Telegram bruges som alert-kanal, ikke som normal UI.

### 11.4 Dashboard på localhost

Når dashboardet ses på `http://127.0.0.1:3000/`, er det et read-only vindue ind i systemets aktuelle state. Det viser ikke automatisk strategikode eller alle Kubernetes-ressourcer. Det viser kun de data, API'et eksponerer: status, PnL, positioner, fills og historik.

Hvis dashboardet er tomt, kan det skyldes flere ting:

- der er ingen fills eller positioner endnu,
- API'et har ikke modtaget NATS-events,
- database har ingen historik,
- adapteren er ikke connected,
- port-forward eller dev server peger forkert,
- systemet kører, men markedet eller strategien har ikke udløst handler.

Derfor skal dashboardet forstås som et observability-værktøj, ikke som bevis for at alle komponenter er aktive. Ved fejlfinding skal man også se Kubernetes pods, logs, NATS og service readiness.

### 11.5 Fejlfinding i distribuerede systemer

I et distribueret system er en fejl sjældent kun ét sted. Hvis en ordre ikke ender hos IBKR, kan fejlen ligge i strategien, Risk Gateway, NATS, adapteren, IB Gateway, broker-sessionen eller selve ordren. Derfor er det nyttigt at følge flowet trin for trin:

1. Sendte strategien en HTTP request?
2. Accepterede Risk Gateway ordren?
3. Blev ordren publiceret på NATS?
4. Modtog adapteren beskeden på `orders.>`?
5. Var adapteren connected?
6. Kaldte adapteren `place_order()`?
7. Returnerede IBKR en fejl eller et fill?
8. Blev broker-eventet publiceret tilbage på NATS?
9. Viste API/dashboard den nye state?

Denne trinvise tilgang er en central læring i projektet. Den gør det lettere at forklare systemet til eksamen og lettere at finde fejl i praksis.

## 12. Sikkerhed, risiko og etik

### 12.1 Teknisk sikkerhed

Trading-systemer bør bygges med en konservativ sikkerhedsmodel. I AmalieTrader betyder det, at strategier ikke skal have direkte brokeradgang. De skal sende ordreintentioner gennem Risk Gateway. Dette reducerer risikoen for, at en fejl i en strategi uden videre kan placere ordrer.

Derudover bruges idempotency keys til at reducere duplicate orders, rate limiting til at bremse order storms, restricted symbols til at blokere uønskede instrumenter og fat-finger checks til at opdage ekstreme limit-priser.

I v0 er nogle sikkerhedselementer stadig manglende eller ufuldstændige. NetworkPolicy bør bruges til at forhindre strategier i at nå IB Gateway direkte. Secrets bør håndteres med en mere robust løsning end almindelige Kubernetes Secrets, hvis systemet bruges seriøst. Dashboardet bør have adgangskontrol, hvis det eksponeres uden for et lokalt miljø.

### 12.2 Trading-risiko

Selvom paper trading ikke bruger rigtige penge, skal systemet designes med live-risiko i tankerne. Vaner fra paper trading kan senere overføres til live trading. Derfor er det vigtigt, at systemet allerede i prototypen har en arkitektur, hvor ordrer valideres og overvåges.

Risk Gateway og risk-monitor har forskellige roller. Risk Gateway er in-path og fanger fejl før en ordre sendes videre. Risk-monitor er out-of-band og fanger tilstande, der opstår over tid eller på account-niveau. Begge lag er nødvendige, fordi de beskytter mod forskellige fejltyper.

### 12.3 Etiske overvejelser

Algoritmisk handel kan påvirke rigtige markeder, særligt hvis systemer handler hurtigt eller med store beløb. Dette projekt er udviklet til paper trading og læring, ikke til markedsmanipulation eller ukontrolleret spekulation. En ansvarlig videreudvikling bør indeholde klare limits, manuel overvågning og en forsigtig overgang fra paper til live.

Der er også et etisk aspekt i at beskrive produktet ærligt. Det ville være forkert at fremstille prototypen som en færdig produktionsplatform. Rapporten gør derfor tydeligt, hvilke dele der er implementeret, og hvilke dele der er fremtidigt arbejde.

### 12.4 Data og credentials

Projektet håndterer potentielt følsomme oplysninger som broker credentials, account IDs og Telegram tokens. Disse må ikke hardcodes i repositoryet. De skal håndteres som secrets i deploymentmiljøet. I en produktionsmodning bør der bruges en løsning som External Secrets, SOPS eller en cloud secret manager.

Account IDs i screenshots og rapport bør vurderes før aflevering. En paper account er mindre følsom end en live account, men det er stadig god praksis at minimere eksponering af credentials og kontooplysninger.

## 13. Diskussion

### 13.1 Platform frem for bot

Den vigtigste designbeslutning er, at AmalieTrader er en platform frem for en bot. En bot kunne være hurtigere at bygge, men den ville skjule mange ansvar i samme kodebase. Platformen kræver mere opsætning, men giver bedre separation, testbarhed og driftsindsigt.

Denne beslutning er fagligt relevant, fordi hovedopgaven skal demonstrere softwareudvikling, ikke kun tradinglogik. Projektet viser microservices, events, deployment, API'er, test, observability og risikovurdering i ét samlet produkt.

### 13.2 Fordele ved arkitekturen

Arkitekturen har flere styrker:

- Strategier kan udvikles uafhængigt af brokerintegration.
- Risk Gateway giver et centralt kontrolpunkt.
- Adapteren isolerer IBKR-kompleksitet.
- NATS reducerer direkte kobling mellem services.
- Risk-monitor kan opdage account-level problemer.
- Dashboardet gør systemets tilstand synlig.
- Helm gør deployment reproducerbar.

Styrken er især, at systemet er eksamensforsvarligt: man kan forklare hvert led i kæden og begrunde, hvorfor det findes.

### 13.3 Ulemper og kompleksitet

Arkitekturen har også ulemper. Flere services betyder flere steder, hvor noget kan gå galt. NATS, IB Gateway, Kubernetes, database og adapter skal alle fungere. For et lille privat tradingprojekt kan det virke tungt sammenlignet med en enkelt script-bot.

Kompleksiteten er dog ikke tilfældig. Den kommer af kravene om kontrol, observability og reproducerbar drift. Hvis målet kun var at placere én paper-ordre, ville arkitekturen være for stor. Hvis målet er at bygge et fundament for flere strategier og risikostyring, er opdelingen mere rimelig.

### 13.4 In-memory state i Risk Gateway

Den største tekniske begrænsning er Risk Gatewayens in-memory state. Den nuværende implementation kan fungere i en prototype, men den er ikke robust ved flere replicas. Duplicate detection, rate limits og halt-state bør deles mellem pods.

Dette er et godt eksempel på forskellen mellem et fungerende v0-produkt og en produktionsmoden løsning. V0 viser designet og regellogikken. Produktionsmodning kræver delt state, migrationsstrategi, failure modes og fail-closed adfærd.

### 13.5 Audit og reconciliation

Projektet har et database schema til audit og historik, men fuld audit persistence og broker-reconciliation er ikke færdiggjort i alle led. Det er vigtigt, fordi brokerens state er den endelige sandhed. Hvis lokal state og broker state afviger, skal systemet kunne opdage og håndtere det.

Reconciliation bør i en senere version sammenligne lokale events med IBKR snapshots for open orders, positions og executions. Ved mismatch bør systemet sende alert og eventuelt stoppe handel, indtil en operatør har vurderet situationen.

### 13.6 Dashboardets rolle

Dashboardet er nyttigt, men det er ikke en komplet driftsplatform. Det viser read-only state og er derfor sikkert afgrænset. Til gengæld kan man ikke bruge det til manual flatten, start/stop af strategier eller ordreannullering. Disse funktioner ville være relevante i en senere version, men de kræver en mere moden auth- og auditmodel.

## 14. Perspektivering

### 14.1 Fuldt strategy framework

En videreudvikling kunne indføre et tydeligere strategy framework. I dag fungerer `strategy-hello` som eksempel og template. En mere moden platform kunne definere en fælles kontrakt for strategier, standardiseret backtesting, market data adapters og en måde at pakke strategier som separate images.

Det ville også være relevant at understøtte mere præcis strategi-state, så en strategi ikke kun holder lokal position i memory, men kan genopbygge state efter restart.

### 14.2 Delt state og Redis

Risk Gatewayens state bør flyttes ud af memory. Redis ville være et oplagt valg til rate limiting, idempotency og halt flags, fordi det er hurtigt og understøtter atomiske operationer. Alternativt kan PostgreSQL bruges, hvis man prioriterer audit over latency.

Delt state ville gøre det muligt at køre flere Risk Gateway replicas uden at miste konsistens. Det ville også gøre restarts mere sikre, fordi idempotency state ikke forsvinder ved pod restart.

### 14.3 Reconciliation og audit trail

En vigtig videreudvikling er fuld broker-reconciliation. Systemet bør periodisk hente brokerens open orders, positions og executions og sammenligne dem med lokal state. Alle forskelle bør logges som audit events og kunne ses i dashboardet.

Audit trail bør være append-only. Det betyder, at man ikke overskriver historik, men gemmer nye events for accepted, rejected, placed, filled, cancelled og failed. Det er særligt vigtigt i finansielle systemer, hvor man skal kunne forklare, hvorfor en handel blev placeret.

### 14.4 Bedre observability

Projektet har metrics, health endpoints, logs og Telegram-alerts. En videre version kunne samle dette i Grafana dashboards med klare alarmer for adapter state, NATS lag, rejected orders, PnL, drawdown og heartbeat.

Dashboardet kunne også udvides med en driftsside, der viser status for hver service og seneste event pr. subject. Det ville gøre fejlfinding lettere for en bruger, der ikke kender Kubernetes-kommandoer.

### 14.5 Manual controls

I live trading er det vigtigt at kunne stoppe strategier og lukke risiko manuelt. En senere version kunne tilføje:

- global halt-knap,
- strategy halt,
- cancel open orders,
- flatten positions,
- read-only/armed/live modes,
- to-person approval for live mode.

Disse funktioner bør ikke bare tilføjes som frontend-knapper. De kræver adgangskontrol, audit og klare regler for, hvilke services der må udføre handlingerne.

### 14.6 Fra paper til live

Overgangen fra paper til live bør ske gradvist. Først bør systemet køre stabilt i paper mode over tid. Dernæst kan man bruge meget lave limits i live mode. Til sidst kan limits langsomt justeres, hvis systemet viser stabilitet.

Før live trading bør følgende være på plads:

- ekstern secret management,
- NetworkPolicy,
- persistent idempotency,
- fuld audit trail,
- reconciliation,
- dokumenterede runbooks,
- monitoring og alerting,
- klare max loss og exposure grænser,
- manuel nødstopprocedure.

## 15. Konklusion

Projektet har undersøgt, hvordan man kan udvikle en Kubernetes-baseret trading-platform, hvor algoritmiske handelsstrategier kan sende ordrer til Interactive Brokers gennem en kontrolleret, observerbar og risikostyret arkitektur.

Resultatet er AmalieTrader, en v0-prototype med flere services: strategi, Risk Gateway, NATS, IBKR-adapter, IB Gateway, risk-monitor, API, dashboard og database. Den centrale kæde er designet, så strategier ikke taler direkte med brokerens API. I stedet passerer ordreintentioner gennem Risk Gateway, publiceres på NATS og håndteres af en central adapter.

Projektet viser, at separation af ansvar er afgørende i et trading-system. Strategien skal fokusere på signaler, Risk Gateway på pre-trade kontroller, adapteren på brokerkommunikation, risk-monitor på account-level overvågning og dashboardet på synlighed. Denne opdeling gør systemet lettere at teste, forklare og videreudvikle.

Problemformuleringens krav om kontrol opfyldes gennem Risk Gateway og circuit breaker. Kravet om observability opfyldes gennem heartbeat, metrics, Telegram-alerts, API og dashboard. Kravet om reproducerbarhed opfyldes gennem Docker og Helm. Projektet opfylder derfor sit formål som teknisk platformprototype til paper trading.

Samtidig er der klare begrænsninger. Risk Gatewayens state er in-memory, audit persistence og broker-reconciliation er kun delvist etableret, og systemet er ikke produktionsklart til live trading. Disse begrænsninger svækker ikke projektets faglige værdi, men markerer grænsen mellem prototype og finansiel produktionsplatform.

Den samlede konklusion er, at AmalieTrader demonstrerer en relevant og realistisk arkitektur for sikker test af handelsalgoritmer. Projektet viser, at en trading-platform bør bygges omkring kontrollerede ordreveje, central brokerintegration og stærk observability, før man overhovedet diskuterer om en strategi er profitabel.

## 16. Litteraturliste

- Erhvervsakademi København. (2025/2026). *Afsluttende projekt (DA), Datamatiker*. Fag- og modulkatalog.
- Erhvervsakademi København. (2024). *Hovedopgaven - en guide, version 2.0*.
- Erhvervsakademi København. (2026). *Hovedopgave Forår 2026 Data-GBG-F24*.
- Interactive Brokers. (u.å.). *TWS API Documentation*. https://interactivebrokers.github.io/tws-api/
- ib_insync. (u.å.). *ib_insync documentation*. https://ib-insync.readthedocs.io/
- NATS. (u.å.). *NATS Documentation*. https://docs.nats.io/
- Kubernetes. (u.å.). *Kubernetes Documentation*. https://kubernetes.io/docs/
- Helm. (u.å.). *Helm Documentation*. https://helm.sh/docs/
- FastAPI. (u.å.). *FastAPI Documentation*. https://fastapi.tiangolo.com/
- Pydantic. (u.å.). *Pydantic Documentation*. https://docs.pydantic.dev/
- Timescale. (u.å.). *TimescaleDB Documentation*. https://docs.timescale.com/
- Next.js. (u.å.). *Next.js Documentation*. https://nextjs.org/docs

TODO: Gennemgå litteraturlisten før aflevering og sørg for, at alle kilder, du henviser til i brødteksten, også står her i samme referenceformat.

## 17. Bilag

### Bilag A: Projektets centrale mapper

```text
services/strategy-hello
services/risk-gateway
services/ibkr-adapter
services/risk-monitor
services/api
services/dashboard
helm/ibkrtrader
```

### Bilag B: Centralt ordreflow

```text
Strategi
  -> HTTP POST /orders
  -> Risk Gateway
  -> NATS beskedbus
  -> ibkr-adapter
  -> IB Gateway
  -> Interactive Brokers
```

### Bilag C: Centrale NATS subjects

```text
orders.<strategy>.<symbol>
fills.<account>.<symbol>
positions.<account>.<symbol>
pnl.<account>
risk.adapter.heartbeat
risk.adapter.disconnected
risk.halt
marketdata.realtime.<symbol>
```

### Bilag D: Forslag til figurer/screenshots

Indsæt følgende figurer i den endelige Word/PDF-version:

1. Arkitekturdiagram over services og ordreflow.
2. Screenshot af dashboardet på `http://127.0.0.1:3000/`.
3. Screenshot af Telegram heartbeat timeout eller halt alert.
4. Screenshot af Kubernetes pods for release `trader`.
5. Uddrag af Risk Gateway checks eller Helm values, hvis der er plads.

### Bilag E: Eksamenstale i kort form

Hvis projektet skal forklares kort til eksamen, kan det siges sådan:

> Jeg har bygget en event-drevet trading-platform, ikke bare en trading-bot. Strategier genererer ordreintentioner, Risk Gateway validerer dem, NATS transporterer accepterede events, en central IBKR-adapter ejer brokerintegrationen, og risk-monitor, API og dashboard observerer systemets tilstand. Projektets fokus er sikker test i paper trading, ikke at bevise en profitabel strategi.
