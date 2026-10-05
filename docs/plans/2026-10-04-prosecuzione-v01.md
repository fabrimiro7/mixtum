# Mixtum — Prosecuzione verificata verso v0.1

## 1. Goal

Portare il checkpoint `2f31ebf` a una v0.1 utilizzabile in ambiente locale/staging: installazione ripetibile, login reale, workspace isolati, percorso Ticket, amministrazione ordinaria, plugin esterni e personalizzazione, aggiornamento e ripristino dimostrati. Questo è il primo significato operativo di «un buon livello». La roadmap successiva resta quella del piano di handoff: capability condivise, AI/RAG e Documents, configuratore, Kubernetes e verticali evoluti.

## 2. Non-goals

Pubblicazione di pacchetti, merge in main, deploy pubblico e migrazione di istanze cliente richiedono una consegna distinta. Il runtime `mixtum-iso` appartiene a un altro checkout e non è l'istanza di prova.

## 3. Current state

Fonte di partenza: [handoff](2026-10-03-stato-e-roadmap-handoff.md). Le prove storiche restano evidenze storiche, da distinguere dalle verifiche del checkout corrente.

- Branch `codex/mixtum-handoff-2026-10-04`, baseline `2f31ebf`, worktree inizialmente pulito.
- Toolchain verificata: Docker 27.4.0, Python 3.12.15 e Node 22.22.3/npm 10.9.8.
- Wheel Platform/Example/Links/Ticket e bundle Console ricostruiti dal sorgente; installazione isolata e `pip check` superati.
- Istanza dedicata `mixtum-v01-local` generata in `/private/tmp`, sulle porte Console 14200, API 18000 e Keycloak 18080. Lo stack `mixtum-iso` è rimasto estraneo.

## 4. Target architecture

Conservare Extension → Plugin → Platform → Core, composizione d'istanza esplicita, contratti pubblici e artefatti coordinati. Keycloak mantiene identità/sessioni, Mixtum membership e autorizzazioni. L'amministrazione di workspace/branding appartiene alla Platform; aziende e abilitazioni Ticket al plugin. Riutilizzare registry, permission, generatori, Makefile e verificatori esistenti. Per ciascun difetto cercare implementazioni equivalenti prima di introdurre codice.

## 5. Security impact

Prove con utenti sintetici, due workspace e risorse dedicate su loopback. Verificare accesso anonimo, token invalidi, oggetti/relazioni estranei, revoche, escalation e reset dello stato frontend. Nessuna auto-associazione per email o riapertura dell'admin password in Keycloak. Secret esclusi da log/report/artefatti. Per l'amministrazione definire policy esplicite e test prima degli endpoint.

## 6. Data/migration impact

Prima istanza vuota e dedicata. Applicare migration con i comandi di preparazione esistenti. Provare su PostgreSQL le nuove migration e la conservazione dei dati; Links legacy richiede mappatura esplicita. Nessuna inversione automatica o cancellazione volumi. Prima di upgrade, snapshot e ripristino verificati con credenziali e versioni corrispondenti.

## 7. Deployment impact

Toolchain isolata, nome progetto e porte distinti dalle istanze esistenti. Artefatti costruiti dal checkout corrente; installazione backend senza import dal sorgente. Container non-root, readiness e preparazione schema separata. Verificare risoluzione dei lock sul target; documentare qualsiasi pin non disponibile prima di modificarlo.

## 8. Milestones

| Gate | Lavoro e file principali | Accettazione | Stato |
|---|---|---|---|
| P0a | Toolchain, requirements/lock, package-lock, Dockerfile, CI | Versioni disponibili, installazione ripetibile, wheel e bundle costruiti | PASS locale |
| P0b | Generatore e `templates/instance` | Nuova istanza, migration PostgreSQL, quattro servizi attivi, health e Console verificati | PASS locale |
| P1 | Auth/workspace, Console, Ticket, branding | Login PKCE, due utenti/workspace, creazione/elenco/dettaglio, dinieghi, logout e persistenza | PASS locale |
| P1a | Amministrazione Platform e Ticket | Operatore autorizzato gestisce configurazioni ordinarie da UI; utenti non autorizzati respinti | PASS locale |
| P2 | Generatore plugin, registry, contratti Console, extension | Plugin esterno da sorgenti e artefatti, reload, seconda composizione e disabilitazione senza perdita dati | PASS locale |
| P3a | Snapshot/restore e release coordinata | Seconda istanza ripristinata con login/dati/media; upgrade mantiene personalizzazioni e dati | PASS locale |
| P3b | Suite, CI, Public Frontend, servizi opzionali e guide | Test PostgreSQL/browser verdi, CI osservata, installazione pulita ripetuta e documentazione coerente | PASS locale; CI GitHub da osservare |

Correggere la prima causa osservata e rieseguire il controllo pertinente. Non aggiungere sottosistemi per aggirare un gate fallito. Dopo P3 valutare la roadmap post-v0.1 con una baseline verificata.

## 9. Test plan

Usare i comandi di `TESTING.md`, gli script in `console/package.json`, `public_frontend/package.json` e `.github/workflows/ci.yml`:

- `python3.12 -m unittest discover -s tests -p 'test_*.py' -q`.
- Suite Django con configurazione SQLite isolata descritta in `TESTING.md`, poi suite PostgreSQL su database dedicato.
- `npm ci`, build e `npm test` Console; build e `npm test -- --watch=false` Public Frontend.
- Verificatori wheel/plugin esistenti e prova browser reale con Keycloak.
- `make install-wheels`, `check`, `wheel-check`, `stage-wheels`, `console-build`, `prepare`, `up` nell'istanza.
- Snapshot cold e restore su secondo progetto; upgrade con dato sentinella e personalizzazioni.

Lo staging automatico è attualmente CI-only: non falsificare `GITHUB_ACTIONS`. Usare il flusso locale oppure adattare esplicitamente il verificatore con preflight e test per percorsi/risorse dedicate.

## 10. Rollout

Solo istanze di prova dedicate. Registrare nomi, percorsi e comandi di arresto; conservare dati e credenziali. Nessun rollout sulle altre istanze. La pubblicazione resta successiva al report di chiusura.

## 11. Removal plan

Rimuovere codice sostituito dopo test e migrazione dei consumer. Aggiornare i rimandi documentali senza perdere lo storico. L'auth Django legacy e gli allegati esclusi da Keycloak richiedono inventario dei consumer prima della rimozione; non considerarli capability documentale pronta.

## 12. Completion criteria

Tutti i gate P0–P3 devono avere evidenza sul codice finale: ambiente, comando, esito e limiti. Applicare `DEFINITION_OF_DONE.md`. Build e test simulati non chiudono login, isolamento o recovery. Il report deve distinguere implementato, verificato e residuo; niente percentuali arbitrarie. La roadmap post-v0.1 rimane aperta e distinta dal primo traguardo.

## Diario delle evidenze

- 2026-10-04: baseline Git pulita confermata; letti workflow d'istanza, template e CI. Avviato preflight delle dipendenze. Nessuna istanza cliente modificata.
- 2026-10-05: installati Python 3.12.15 e Node 22.22.3; costruiti wheel e bundle Console due volte. `npm ci` ha risolto 418 pacchetti con zero vulnerabilità note.
- 2026-10-05: generata e avviata `mixtum-v01-local`; migration PostgreSQL complete, quattro servizi attivi, live/readiness, configurazione Console e discovery OIDC verificati.
- 2026-10-05: individuato un difetto reale nel realm: l'elenco esplicito degli scope ometteva `basic`, quindi gli access token Keycloak 26 non contenevano `sub`. Aggiunto lo scope ai due client di prodotto e al client effimero CI, con test di contratto.
- 2026-10-05: Alice e Bob hanno completato Authorization Code + PKCE, cambio password temporanea, required action profilo, sessione backend autenticata e logout. Dopo il bootstrap esplicito, ciascuno vede solo il proprio workspace, branding e Ticket; tentativi diretti verso il workspace estraneo ricevono HTTP 403. Il verificatore controlla anche header bearer, reset dello stato workspace e risposta della sessione backend, evitando il precedente falso positivo della sola presenza della Dashboard.
- 2026-10-05: implementata l'amministrazione Console per workspace, membership, gestori e branding, con bootstrap centrale esplicito su `(issuer, subject)`, `is_superuser` come unica autorità globale, audit e protezione transazionale dell'ultimo gestore. La configurazione Ticket applica membership e isolamento workspace anche a richiedenti, referenti, operatori e responsabili assistenza.
- 2026-10-05: suite repository (78 test), suite Django (175 test), Console (23 test) e Public Frontend (4 test) verdi. Build Console/Public, migration check, wheel check e immagini Docker completati. Il gate npm inizialmente fallito nel sandbox è passato con Node 22.22.3, rete e cache npm accessibili; `npm audit` non ha rilevato vulnerabilità note.
- 2026-10-05: plugin esterno verificato da wheel e tarball senza dipendenza dai sorgenti, inclusi reload Django/Angular e immagine Docker. Seconda composizione Ticket + Links + extension dimostrativa verificata con branding differente; disabilitazione e riabilitazione hanno rimosso e ripristinato API/pagine senza perdere i dati Ticket.
- 2026-10-05: snapshot cold e restore verificati su un secondo progetto Docker. Dopo il restore sono passati login browser, membership, Ticket, branding, media e diniego cross-workspace. Provato anche l'aggiornamento dagli artefatti baseline a quelli finali conservando dati e personalizzazioni. Gli artefatti finali coordinati includono wheel, bundle Console/Public e checksum.
- 2026-10-05: provato il rollback coerente su `mixtum-v01-rollback-proof`, ripristinando snapshot, credenziali, lock, wheel, composizione e bundle Console baseline. Il database è rimasto alle migration baseline e Alice ha completato login PKCE, lettura Ticket, diniego sul workspace estraneo e logout. Nessun downgrade del solo codice è stato usato.
- 2026-10-05: il client OIDC separato `mixtum-public` ha completato PKCE, sessione, selezione workspace e logout. Sono dichiarate verificate soltanto le composizioni Ticket e Ticket + Links + demo_support, con Public Frontend opzionale; S3, AI/RAG, Documents, configuratore visuale e Kubernetes restano fuori dal perimetro v0.1.
