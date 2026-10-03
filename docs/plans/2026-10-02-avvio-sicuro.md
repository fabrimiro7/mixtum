# ExecPlan A0–A3 — Avvio e build sicuri

## 1. Goal

Rendere setup, build e avvio ripetibili senza cancellazione implicita di dati o inclusione di segreti nelle immagini. Dimostrare i comportamenti con test simulati e, se possibile, con una prova Docker isolata.

## 2. Non-goals

Nessun upgrade applicativo, modifica schema, Keycloak, Ticket, plugin, provisioning cloud o rollout pubblico.

## 3. Current state

Prima dell'intervento, `scripts/setup.sh` rimuoveva il volume PostgreSQL quando `.env` mancava; `Dockerfile` copiava tutto il contesto senza escludere `.env`; l'entrypoint applicava migration e statici all'avvio web. Compose avviava worker e scheduler di default e pubblicava DB/Redis nell'override locale. Baseline: sintassi di 151 file Python e script shell superata; Compose locale/prod valido; check Django corrente superato; check Keycloak fallito per import inesistente; build frontend bloccate da dipendenze locali mancanti. 31 metodi di test individuati, 15 vuoti, test workspace vuoto.

## 4. Target architecture

Stessa struttura modulare Extension → Plugin → Platform → Core. Nessun nuovo runtime: setup prepara `.env`, immagine, DB, migration e web nell'ordine; entrypoint esegue un solo ruolo; statici nell'immagine durante la build; Compose mantiene servizi opzionali sotto profilo.

## 5. Security impact

Volume esistente senza credenziali causa arresto prima di side effect. `.env*` reali esclusi dal contesto. Nessun secret stampato. Porte locali applicative su loopback; DB/Redis non pubblicati per default. Nessun cambiamento a auth, authorization o workspace isolation; la modalità Keycloak rimane non validata.

## 6. Data/migration impact

Nessuna nuova migration o modifica schema. Migration esistenti eseguite con comando esplicito di preparazione. Un riavvio del web non le riesegue. La prova isolata usa soltanto un volume col nome dedicato.

## 7. Deployment impact

`make prod` e `scripts/deploy.sh` preparano immagine e migration prima del web. Nessun deployment pubblico eseguito. Resta necessario revisionare credenziali, TLS, routing e autenticazione prima di dichiarare pronta la produzione. Console/Keycloak restano opzionali.

## 8. Milestones

- A0: registrare baseline e proteggere il working tree dell'utente; verificare `git status`.
- A1: setup fail-safe e `.dockerignore`; test simulati su volume, errori e secret.
- A2: separare entrypoint e preparazione; `bash -n`, test simulati e `docker compose config`.
- A3: build e smoke con progetto Docker dedicato, sentinella nel DB e riavvio, solo dopo verifica di assenza di risorse omonime.

## 9. Test plan

`python -m unittest discover -s tests -p 'test_bootstrap.py' -v`; `bash -n` sugli script; `docker compose config --quiet` locale/prod; `python manage.py check` corrente; prova Docker isolata se immagini e rete sono disponibili. I test simulati verificano l'ordine dei comandi, non solo la presenza di stringhe.

## 10. Rollout

Nessuno in questa consegna. Il codice può essere ripristinato via Git senza toccare i volumi. Il rollback del codice non recupera secret già smarriti; eventuali immagini pubblicate con secret richiedono audit e rotazione separati.

## 11. Removal plan

Eliminati il ramo di reset implicito nel setup e le migration/collectstatic impliciti nell'entrypoint. Non rimuovere automaticamente volumi di prova o istanze esistenti.

## 12. Completion criteria

Test di regressione e validazione Compose superati; contesto di build verificato; prova isolata e persistenza documentate, oppure limite di esecuzione dichiarato. Report finale con security checks, impatto deployment e rischi residui.

## Risultati A0–A3 (2026-10-02)

La chiusura successiva del setup e la baseline delle dipendenze sono registrate in [2026-10-02-baseline-dipendenze.md](2026-10-02-baseline-dipendenze.md).

- Otto test di bootstrap con comandi simulati superati; `bash -n` sugli script, `docker compose config --quiet` locale/prod e `python manage.py check` superati.
- Build Docker del solo web nel progetto `mixtum-a3-20261002` superata; gli statici sono stati raccolti nell'immagine. Ispezione nell'immagine: `/app/.env` assente, `.env.example` presente, `staticfiles` presente, dipendenze locali frontend assenti. Una sentinella temporanea non sensibile `.env.a3-sentinel` è stata esclusa dalla build e poi rimossa dal workspace.
- Il volume `mixtum-a3-20261002_postgres_data` era assente prima della prova. Creato un DB isolato senza porte host; migration applicate solo lì; web avviato e `manage.py check` superato nel container.
- Tabella sentinella `bootstrap_sentinel` nel DB isolato: una riga prima e dopo il riavvio di DB e web. I container A3 sono stati fermati; volume e container fermati rimangono disponibili per ispezione, senza pulizia distruttiva.
- Non eseguito un deployment pubblico né verificata la modalità Keycloak. La Console e il Public Frontend non sono stati costruiti (dipendenze locali assenti nella baseline). La configurazione TLS/Certbot non è stata provata end-to-end.
