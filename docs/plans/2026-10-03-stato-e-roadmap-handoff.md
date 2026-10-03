# Mixtum — Stato consolidato e piano di prosecuzione sul secondo Mac

Aggiornato il **3 ottobre 2026**, dopo la preparazione di `mac-handoff-2026-10-03-r3.tar.gz`.

Questo documento è il punto di partenza per il nuovo Codex. Riassume tutti gli obiettivi concordati, distingue implementazione e verifica, e ordina il lavoro ancora necessario. Il [piano storico](2026-10-02-platform-v01.md) conserva i dettagli delle prove: le sue sezioni cronologiche descrivono anche limiti successivamente risolti e non vanno lette tutte come stato corrente.

## 1. Risultato che vogliamo ottenere

Mixtum deve diventare una piattaforma che uno sviluppatore o un agente possa installare, avviare, personalizzare e ampliare rapidamente con normali plugin Django/Angular, senza creare un fork del framework per ogni cliente.

La prima release, **Mixtum Platform v0.1**, deve dimostrare:

1. Creazione riproducibile di una nuova istanza con backend, Console, PostgreSQL e Keycloak.
2. Login reale e isolamento di utenti, workspace, oggetti e relazioni.
3. Plugin con modelli, API e pagine Console, sia nel checkout sia da repository esterno.
4. Reload backend/frontend durante lo sviluppo e installazione da artefatti compilati.
5. Configurazione, branding ed extension posseduti dall'istanza, senza modificare Core e plugin standard.
6. Aggiornamento della piattaforma senza ricopiare personalizzazioni cliente.
7. Procedura verificata di avvio, arresto, persistenza, backup e ripristino.

Dopo la v0.1 rimangono nella roadmap capability condivise, AI/RAG, Documents, configuratore visuale e distribuzione Kubernetes. Non sono stati cancellati dagli obiettivi.

## 2. Stato reale, in una pagina

**Esiste un'implementazione ampia con prove locali e un pacchetto trasferibile. La v0.1 non è ancora verificata come sistema completo.** Il prossimo risultato deve essere un'istanza funzionante sul secondo Mac, seguita dalla chiusura dei difetti osservati.

| Consegna | Implementazione presente | Evidenza disponibile | Da chiudere |
|---|---|---|---|
| 1. Stack aggiornato | Versioni concordate, lock/constraints, build e CI | Build/test locali registrati; immagine backend costruita in una prova precedente | Build pulita dello snapshot e CI osservata; verifica delle schermate |
| 2. Identità e workspace | Backend Keycloak, PKCE Console/Public, membership e scope API | Test token/JWKS, accesso negato e isolamento su SQLite | Login reale, PostgreSQL, due utenti/workspace nel browser; amministrazione operativa |
| 3. Plugin e confini | Example, Links, Ticket minimo, extension demo; registry e contratto Console | Prove locali wheel/npm, checkout esterno e reload in fasi precedenti | Ripetere sullo stato finale; plugin esterno nell'immagine; seconda composizione completa |
| 4. Istanze e release | Template, generatori, registrazione, skill, immagini da wheel, snapshot/restore | Generazione e packaging provati; test degli strumenti | Stack reale, recovery reale, aggiornamento e release coordinata dimostrati |
| 5. Capability e AI/RAG | Esistono moduli legacy, ma non la capability condivisa prevista | Nessuna prova che soddisfi questa consegna | Runtime condiviso, Documents, secondo consumatore e sicurezza RAG |
| 6. Configuratore e Kubernetes | Nessuna consegna verificata | Nessun gate completato | UI sul flusso stabile, equivalenza con script/skill, Helm e cluster di prova |

Non assegnare percentuali arbitrarie di completamento: i gate end-to-end aperti possono ancora rivelare problemi sostanziali.

## 3. Materiale da trasferire e attendibilità delle prove

Il pacchetto `dist/mac-handoff-2026-10-03-r3.tar.gz` contiene:

- snapshot `mixtum-source.tar.gz` con 512 file sorgente selezionati dal worktree corrente;
- wheel `0.1.0` di Platform, Example, Links e Ticket;
- bundle Console `mixtum-console-0.1.0.tar.gz` e `SHA256SUMS`.

Include modifiche non committate e file nuovi. **Non contiene la directory `.git`**, la relativa storia, `.env`, dati, volumi, dipendenze locali o immagini Docker. Non sostituire lo snapshot con un clone del remoto: non è dimostrato che il remoto contenga questo lavoro. I checksum verificano l'integrità del trasferimento, non sono una firma della release.

**Percorso preferito per il secondo Mac:** usare il branch Git `codex/mixtum-handoff-2026-10-04`, che include questo piano e conserva la storia delle modifiche. Il pacchetto r3 resta una copia di sicurezza per la prova locale. Se si usa r3, questo piano va copiato separatamente in `mixtum-source/docs/plans/`, perché è stato scritto dopo la creazione dell'archivio. I link qui sono relativi per restare utilizzabili sul nuovo host.

### Ultime verifiche registrate sul Mac sorgente

| Verifica | Risultato e limite |
|---|---|
| Suite repository | 78 test PASS durante la preparazione dell'handoff; diversi test infrastrutturali simulano Docker |
| Suite Django | 152 test PASS su SQLite isolato nel turno precedente all'handoff; dopo l'ultima validazione degli argomenti del comando workspace, 5 test mirati nuovamente PASS |
| Wheel Platform | PASS: 139 file, migration incluse, controllo del contenuto |
| Trasferimento | PASS: estrazione del pacchetto, checksum, generazione istanza, staging wheel, Compose config |
| Frontend | Build e test browser riusciti in precedenza; ultime modifiche branding coperte da build e 5 test mirati. Suite Console completa dello stato finale da rieseguire |
| Login Keycloak, stack completo, recovery | NOT RUN sullo snapshot finale |
| CI GitHub | Workflow presente; nessuna esecuzione su runner osservata verde |

Il vecchio Mac ha meno di 1 GiB libero e Docker non risponde. Un precedente tentativo ha prodotto errori I/O del filesystem interno Docker. Questo spiega il blocco locale, ma non prova che il codice funzioni altrove. Non riparare il vecchio Docker come prerequisito della prova sul nuovo Mac.

## 4. Decisioni architetturali da conservare

- Modular monolith e direzione **Extension → Plugin → Platform → Core**.
- Core senza regole Ticket, aziende clienti o configurazioni di un cliente specifico.
- Plugin ordinari Django/Angular: `models.py`, `views.py`, serializer, servizi, migration e componenti. Backend e frontend possono condividere un repository plugin.
- Angular compone i contributi alla build; Django compone app e URL all'avvio. Nessuna installazione dinamica arbitraria di codice in produzione.
- Console condivisa; Public Frontend indipendente e facoltativo.
- Keycloak possiede identità e sessioni; Mixtum possiede membership e autorizzazioni applicative. Collegamento `(issuer, subject)`, senza auto-link email o conversione automatica di ruoli in privilegi locali.
- Release inizialmente coordinate. Un manifest non dimostra compatibilità: servono installazione e prove.
- Disabilitare un plugin conserva i dati; non invertire migration o cancellare tabelle automaticamente.
- Preservare app label, tabelle e storia delle migration durante gli spostamenti.
- Riutilizzare Make, script e contratti esistenti. Nuove astrazioni solo per esigenze dimostrate.

I pin attuali sono Django **6.1.1**, Angular **22.2.1**, CLI **22.2.0**, Tailwind **4.3.3**, Python **3.12** e Node **22.22.3**. Sono i valori del repository, non una nuova verifica online delle versioni più recenti. In caso di problemi di disponibilità/compatibilità documentare la causa prima di proporre cambi di target.

## 5. Mappa concreta del codice esistente

| Area | File/cartelle da leggere |
|---|---|
| Regole di lavoro | `AGENTS.md`, `.agent/PLANS.md`, `ARCHITECTURE.md`, `SECURITY.md`, `TESTING.md`, `DEFINITION_OF_DONE.md` |
| Identità e workspace | `base_modules/user_manager/auth_keycloak.py`, `models.py`, `base_modules/workspace/permissions.py`, `views.py`, `management/commands/grant_workspace_member.py` |
| Console | `console/`, `packages/console-api/`; script `npm test` in `console/package.json` |
| Public Frontend | `public_frontend/`; non incluso come servizio nel template d'istanza iniziale |
| Composizione | `mixtum_core/plugin_registry.py`, `mixtum_instance/`, `templates/instance/mixtum_instance/`, `templates/instance/console/plugins.ts` |
| Plugin ed extension | `plugins/plugin_example/`, `plugins/links/`, `plugins/ticket/`, `extensions/demo_support/` |
| Creazione e packaging | `scripts/create-project.sh`, `create-plugin.py`, `package-console-bundle.py`, `prepare-mac-handoff.py`, `templates/instance/tools/register-plugin.py` |
| Istanza distribuita | `templates/instance/Makefile`, `Dockerfile`, `compose.yaml`, `README.md` |
| Prove esterne/staging | `scripts/verify-external-plugin.py`, `verify-platform-wheel.py`, `verify-instance-staging.py`, `.github/workflows/ci.yml` |

Il template abilita **Ticket soltanto** e nessuna extension. Avere quattro wheel nella cartella non abilita quattro plugin. Per altre composizioni servono requisiti backend, registrazioni e selezione coerenti.

Il bundle Console contiene sorgenti coordinati e lockfile da compilare. Le prove npm dei singoli plugin sono distinte da questo bundle. L'extension demo esiste nel checkout e ha prove locali; il pacchetto trasferito non contiene un suo wheel dedicato. La sua distribuzione indipendente deve ancora essere verificata.

## 6. Ordine di lavoro sul nuovo Mac

### P0 — Portare in esecuzione lo snapshot

Seguire [la guida al trasferimento](../engineering/mac-handoff.md) e poi [la guida d'istanza](../../templates/instance/README.md). Verificare Python 3.12, Node 22.22.3, npm, Make, Docker Compose e spazio libero. Servono Internet e immagini/dipendenze terze; il pacchetto non è offline.

1. Verificare checksum ed estrarre i sorgenti.
2. Creare una directory d'istanza nuova, esterna ai sorgenti, con nome progetto distinto.
3. Eseguire `make stage-wheels`, `make console-build`, validazione Compose, `make prepare`, `make up` come nella guida.
4. Verificare servizi e risposte di `/health/live/`, `/health/ready/` e Console su `127.0.0.1:4200`.
5. Se un passaggio fallisce, correggere la prima causa concreta e ripetere quel passaggio. Conservare comando, exit code ed errore redatto.

**Uscita:** backend, Console, PostgreSQL e Keycloak attivi; build della Console e migration terminate senza errori. Questo checkpoint non dimostra ancora login o isolamento.

### P1 — Dimostrare login e un percorso applicativo completo

1. Creare un utente col tool locale Keycloak dell'istanza; completare login PKCE e cambio della password temporanea.
2. Concedere la prima membership con `grant_workspace_member` usando il subject già verificato. Per un workspace aggiuntivo usare la conferma esplicita descritta nel README.
3. Preparare due utenti e due workspace; verificare selezione, cambio workspace, logout, accesso negato a workspace/oggetti estranei e assenza di privilegi globali automatici.
4. Verificare branding globale e override del workspace, inclusi reset dopo logout o diniego.
5. Preparare in modo esplicito i dati minimi del caso applicativo e provare creazione, elenco e dettaglio nel browser.
6. Arrestare e riavviare l'istanza; verificare un dato sentinella e le identità persistenti.

**Problema da affrontare subito:** in modalità Keycloak `/admin/` Django è disabilitato. I comandi utente/membership esistono, ma manca un flusso completo per amministrare branding, aziende e abilitazioni Ticket. Una nuova istanza Ticket senza questi dati non offre ancora un percorso utile di creazione ticket. Usare per la prova un provisioning locale esplicito su dati dedicati, poi definire il flusso amministrativo minimo con policy e test; non assegnare `is_staff` indiscriminatamente come scorciatoia. Le regole dell'assistenza restano nel plugin.

**Uscita:** una dimostrazione browser ripetibile con identità vere, dati utilizzabili, isolamento e persistenza. Registrare anche eventuali difetti UX o di layout.

### P2 — Chiudere la prova plugin e personalizzazione

1. Provare Links come secondo caso e una seconda composizione d'istanza.
2. Generare un plugin esterno con lo script esistente; registrarlo nell'istanza e provare dati/API/pagina.
3. Provare reload Django editable e reload Angular cambiando realmente un file senza reinstallarlo a ogni salvataggio.
4. Costruire wheel e tarball npm; provarli in una nuova istanza senza dipendere dai sorgenti del plugin.
5. Provare il wheel esterno dentro l'immagine Docker dell'istanza.
6. Disabilitare il plugin e verificare assenza di API/pagine/attività proprie, conservando i dati.
7. Dimostrare branding/composizione differenti e un'extension funzionante con le stesse versioni Mixtum.

Usare `scripts/verify-external-plugin.py --help` e la skill `.agents/skills/mixtum-instance-workflow/SKILL.md`; esistono già verificatori per backend, frontend, immagini e reload. Misurare passaggi, tempi e interventi manuali richiesti. Correggere i problemi osservati prima di aggiungere altra automazione.

**Uscita:** plugin locale/esterno e da artefatti, reload e personalizzazione provati sullo stato finale senza modificare Core o importare internals della Console.

### P3 — Chiudere la v0.1

1. Eseguire test su PostgreSQL e l'intera pipeline CI su un runner osservabile.
2. Provare snapshot cold e restore in una seconda istanza dedicata: configurazione/credenziali originali, versioni corrispondenti e nome progetto distinto. Verificare login, dati e media dopo il restore.
3. Dimostrare un aggiornamento coordinato di artefatti che conservi personalizzazioni e dati; definire recovery/rollback coerente con le migration.
4. Completare il flusso amministrativo minimo necessario a usare l'istanza senza shell per ogni operazione ordinaria; distinguere responsabilità platform e Ticket.
5. Verificare Public Frontend opzionale e client OIDC distinto quando abilitato.
6. Consolidare la selezione dei servizi opzionali realmente supportati (worker/Redis, storage, Public Frontend), con messaggi chiari per configurazioni non supportate.
7. Completare review sicurezza, documentazione, versionamento degli artefatti e prova da installazione pulita. Definire il canale di distribuzione; i pacchetti locali `0.1.0` non sono pubblicati automaticamente.

**Uscita v0.1:** sviluppatore/agente crea un'istanza, accede, usa workspace, aggiunge/modifica un plugin e costruisce la distribuzione; seconda istanza personalizzata, aggiornamento e recovery dimostrati. Nessun rollout pubblico implicito.

## 7. Lavoro successivo rispetto a tutti gli obiettivi

### Consegna 5 — Capability condivise e AI/RAG

Da implementare dopo i gate v0.1:

- Consolidare storage privato, notifiche e attività asincrone sulla base di consumatori reali.
- Un runtime AI condiviso per provider, output strutturato, tool, tracing e contabilizzazione; adapter HTTP compatibile con API OpenAI e provider simulato per test.
- Documents minimo: caricamento privato, elaborazione, indicizzazione e ricerca autorizzata.
- Qdrant opzionale come adapter; vLLM opzionale come infrastruttura.
- Workspace e permessi applicati prima di esporre documenti o risultati al modello.
- Secondo consumatore che usi lo stesso runtime; prove di revoca, cancellazione, reindicizzazione, input ostili e isolamento.

**Uscita:** due consumatori condividono le primitive e il cambio di provider non richiede riscrivere i verticali. Le integrazioni legacy presenti non costituiscono questa consegna.

### Consegna 6 — Configuratore e distribuzioni

Da implementare sul workflow d'istanza già verificato:

- UI per plugin compatibili, capability, branding e Public Frontend.
- Validazione dipendenze, riepilogo e generazione dello stesso progetto prodotto da script/skill.
- Riferimenti ai secret senza esportarne i valori.
- Chart Helm con migration job, probe, servizi opzionali e verifica su cluster di test.

**Uscita:** configuratore, script e skill producono configurazioni equivalenti, con una sola implementazione del provisioning. Marketplace e pubblicazione cloud richiedono una fase propria con account, infrastruttura e politiche definite.

## 8. Critiche iniziali e loro stato

| Critica | Risposta presente | Prova ancora necessaria |
|---|---|---|
| Fondazione troppo grande e complessità crescente | Setup sicuro, comandi e template esistenti | Portare ora lo stack a un risultato visibile; evitare altre sottofasi senza un errore o bisogno concreto |
| Developer experience promessa | Generatore, registrazione, skill e prove locali di reload | Percorso completo sul nuovo Mac, tempi/passaggi misurati |
| Modularità soltanto nominale | Registry, contratto Console, wheel/npm e plugin esterno | Immagine completa, extension distribuita e seconda composizione |
| Sicurezza sacrificata al packaging | Token verificati, scope server-side, secret esclusi, test negativi | Keycloak/PostgreSQL/browser reali, servizi e storage reali |
| Piattaforma costruita intorno a Ticket | Links e extension come altre prove; dominio Ticket nel plugin | Mantenere questi confini durante provisioning e nuova amministrazione |
| Lifecycle e aggiornamenti ambigui | Disabilitazione senza cancellazione, release coordinate | Update e recovery reali, compatibilità e operazioni documentate |

## 9. Rischi, dati e limiti da non perdere nel passaggio

- **Schema:** sono presenti migration nuove per `ExternalIdentity`, scope workspace di Links e Ticket. Le prove locali successive alla baseline sono principalmente SQLite; non trattarle come upgrade PostgreSQL già verificato.
- **Legacy Links:** app label e storia conservate; vecchi record senza workspace restano invisibili alla nuova API. Serve mappatura esplicita, non un backfill indovinato. Vedere [transizione Links](../engineering/links-transition.md).
- **Auth legacy:** `AUTH_MODE=django` esiste ancora per transizione; in Keycloak vecchi endpoint non isolati e admin locale sono esclusi. L'eliminazione definitiva richiede inventario e passaggio dei consumer.
- **Allegati legacy:** ownership, download privato e limite dimensione migliorati, ma il modello non è workspace-scoped. Non riaprirlo in Keycloak come capability Documents. S3, policy bucket e gestione di vecchi URL richiedono prove specifiche.
- **Dipendenze:** `django-celery-beat` usa un commit upstream fissato per compatibilità Django 6.1; il lock Python deriva dalla baseline Linux. Verificare risoluzione sui target e sostituire il workaround solo con compatibilità dimostrata.
- **Frontend:** la suite Console va lanciata con `npm test`, che prepara pacchetti compilati in un ambiente temporaneo. Un `ng test` diretto ha prodotto errori nei test plugin. Il wrapper completo sullo stato finale va rieseguito con spazio sufficiente.
- **Staging automatico:** `scripts/verify-instance-staging.py` è CI-only e usa `/tmp/mixtum-wheel-proof`. Non impostare `GITHUB_ACTIONS=true` sul Mac per aggirarne i controlli; seguire la prova locale oppure adattare esplicitamente il verificatore con percorsi/risorse controllati.
- **Produzione:** Keycloak `start-dev`, TLS/routing, secret management, S3 e altri servizi reali non hanno una verifica complessiva di produzione. I servizi locali sono su loopback.
- **Versionamento:** il checkpoint vive nel branch `codex/mixtum-handoff-2026-10-04`; non fonderlo direttamente in `main`. La copia r3 non ha storia Git. Sul secondo Mac continuare sul branch con commit separati per prove e pulizia; revisionare le differenze prima di integrare in `main`.

## 10. Comandi di verifica già presenti

Dalla radice sorgenti, con dipendenze backend disponibili in un ambiente dedicato e una baseline Git locale inizializzata dopo l'estrazione:

```sh
python3.12 -m unittest discover -s tests -p 'test_*.py' -q
SECRET_KEY=test-only-secret POSTGRES_HOST= USE_S3=0 AUTH_MODE=django MIXTUM_SQLITE_TEST_DB=:memory: DJANGO_SETTINGS_MODULE=tests.fixtures.sqlite_settings python3.12 manage.py test --noinput
python3.12 scripts/verify-external-plugin.py --help
```

Il test di esportazione `tests/test_mac_handoff.py` chiama `git ls-files`: sullo snapshot privo di `.git` fallirà finché non esiste un repository locale. Questa precondizione riguarda il verificatore di packaging, non l'avvio dell'istanza. Se il sorgente è stato estratto dentro un altro repository, controllare prima la radice Git per evitare un inventario errato; inizializzare una baseline autonoma e non pubblicarla automaticamente.

Il secondo comando usa SQLite temporaneo; il test JWKS richiede una porta loopback. Per frontend leggere gli script effettivi in `console/package.json`, `public_frontend/package.json` e il workflow CI; installare dai lockfile, usare il wrapper Console e costruire gli artefatti. Non installare dipendenze nel Python globale. `make install-wheels` dell'istanza prepara un virtualenv, ma lo smoke Docker iniziale può seguire il percorso con wheel già pronti della guida handoff.

Non rieseguire continuamente l'intera suite per cambi documentali: eseguire controlli pertinenti dopo ogni fix e allargare la verifica alla chiusura del risultato.

## 11. Come aggiornare questo piano

Per ciascun checkpoint annotare: data, sorgenti/artefatti usati, comando, ambiente, risultato, prima causa in caso di errore e lavoro residuo. Usare **PASS**, **FAIL**, **NOT RUN** e **DA IMPLEMENTARE** con significato distinto. Un test simulato non chiude una prova reale; una build non chiude login, permessi o recovery.

I risultati visibili da comunicare sono P0 (stack), P1 (uso reale), P2 (plugin/personalizzazione), P3 (v0.1). Proseguire autonomamente su implementazione, test e correzioni autorizzate; richiedere una decisione quando cambia il prodotto, servono risorse esterne o occorre una migrazione distruttiva.

## 12. Messaggio pronto per il nuovo Codex

> Leggi prima `docs/plans/2026-10-03-stato-e-roadmap-handoff.md` e le regole di `AGENTS.md`. Hai ricevuto uno snapshot con modifiche non committate, senza storia Git; non sostituirlo con un clone. L'obiettivo immediato è P0 e P1: avviare una nuova istanza da wheel e bundle Console su questo Mac, completare login Keycloak e un flusso applicativo reale, verificare due utenti/workspace e persistenza. Usa i comandi esistenti e correggi i difetti osservati fino al risultato; non ricominciare a progettare la piattaforma né aggiungere funzionalità prima della prova. Conserva dati e credenziali, usa risorse dedicate e aggiorna il piano con evidenze PASS/FAIL/NOT RUN. Dopo questa prova prosegui nell'ordine P2 e P3; AI/RAG e configuratore restano le consegne successive. Non dichiarare la v0.1 completa finché i gate indicati non sono dimostrati.
