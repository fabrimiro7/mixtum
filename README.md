# Mixtum Framework

Backend Django con **base modules** riutilizzabili (utenti, workspace, email, integrazioni) e **plugin** per estendere le funzionalità. Supporta deployment in sviluppo (locale) e in produzione con SSL automatico Let's Encrypt.

---

## Documentazione

Guide pratiche per sviluppare con Mixtum:

- **[Architettura](ARCHITECTURE.md)** — Confini Core, Platform, Plugin ed Extension.
- **[Contratto di sicurezza](SECURITY.md)** — Autenticazione, autorizzazione e isolamento workspace.
- **[Composizione plugin](docs/engineering/plugin-composition.md)** — Contratto e prova locale di backend, Console e reload del plugin example.
- **[Transizione Links](docs/engineering/links-transition.md)** — Secondo plugin, isolamento workspace e trattamento dei dati legacy.
- **[Packaging backend](docs/engineering/platform-packaging.md)** — Wheel della piattaforma, vincoli di dipendenza e prova da istanza separata.
- **[Allegati legacy](docs/engineering/attachments-legacy.md)** — Accesso per proprietario, download privato e limiti dell'upload in modalità Django.

Per creare una **nuova istanza separata** senza copiare il framework nel progetto cliente:

```bash
bash scripts/create-project.sh /percorso/nuova-istanza
cd /percorso/nuova-istanza
make install-wheels WHEELHOUSE=/percorso/wheelhouse
make check
make console-build CONSOLE_BUNDLE=/percorso/mixtum-console-0.1.0.tar.gz
```

Il template e i suoi limiti sono documentati in [templates/instance/README.md](templates/instance/README.md). Wheel e bundle vengono costruiti dal checkout ma non sono ancora pubblicati; l'avvio end-to-end con Docker resta un gate della release v0.1. Il vecchio `create-project.sh` che generava un `*_core` derivato è stato sostituito.
Anche il vecchio target `make update-mixtum`, che copiava directory dal remote Git sopra il progetto, è stato rimosso. Le istanze dichiarano dipendenze versionate e conservano le proprie extension; una procedura di upgrade e rollback su staging resta da provare prima della release.
Per creare un plugin ordinario in un checkout separato, usa `python3 scripts/create-plugin.py customer_portal /percorso/customer-portal`. Produce package Django, migration, API e test workspace-scoped, più un package Angular con pagina Console. Il [README generato](templates/plugin/README.md) descrive come costruire wheel e tarball; la registrazione e l'abilitazione nell'istanza restano esplicite. Il comando rifiuta una destinazione già esistente e non modifica il framework o i dati dell'istanza.

Per guidare un agente nello stesso flusso, è disponibile la skill sperimentale [mixtum-instance-workflow](.agents/skills/mixtum-instance-workflow/SKILL.md). La build da wheel/tarball esterni, l'installazione npm standalone e il reload frontend del plugin generato tramite `make console-dev` sono provati; release pubblicata e staging reale restano da verificare.

---

## Requisiti di sistema

- **Docker Engine** (es. 20.10+) e **Docker Compose** v2 (`docker compose`).
- **Make** (opzionale ma consigliato per i comandi sotto).
- Per la **produzione**:
  - Dominio con DNS che punta al server.
  - Porte **80** e **443** aperte in ingresso.

---

## Avvio in locale (sviluppo)

### 1. Clonare il repository ed entrare nella cartella

```bash
cd /path/to/mixtum-02
```

### 2. File `.env`

Non creare manualmente `.env` per un'istanza nuova: `make setup` lo genera con credenziali casuali e permessi limitati. Se `.env` esiste già, il setup lo riusa senza cambiare le credenziali. Se manca ma esiste il volume PostgreSQL della stessa istanza, il setup si interrompe: recupera la configurazione originale o scegli una nuova istanza; non eliminare il volume.

`SECRET_KEY` e `POSTGRES_PASSWORD` non hanno più un valore di fallback. Se una configurazione esistente è incompleta o usa `SECRET_KEY=changeme`, il setup si ferma senza rigenerare credenziali: recupera i valori originali prima di riavviare l'istanza. Cambiare soltanto la password nel file `.env` non modifica quella già registrata in PostgreSQL.

Lo storage S3 è facoltativo e disattivato per impostazione predefinita. Se imposti `USE_S3=1`, devi configurare almeno `AWS_STORAGE_BUCKET_NAME`: un bucket mancante interrompe l'avvio invece di passare silenziosamente ai file locali. L'effettivo accesso al provider S3 richiede una prova separata con credenziali e bucket dell'istanza.
Le URL dei media S3 sono firmate per impostazione predefinita. Se un'istanza esistente usava intenzionalmente URL pubbliche senza `AWS_QUERYSTRING_AUTH` in `.env`, valuta l'impatto sui client prima dell'aggiornamento; l'accesso pubblico va scelto esplicitamente con `AWS_QUERYSTRING_AUTH=0` e non è adatto a file privati.

### 3. Primo avvio (setup completo)

Esegui il setup locale: build del backend, avvio del database, migration esplicite e avvio del web.

```bash
make setup
```

Oppure, senza Make:

```bash
bash scripts/setup.sh
```

Il setup non avvia Redis, worker, Console o Keycloak. Le funzionalità che li richiedono non sono disponibili in questa configurazione minima.

### Setup di istanze parallele (stesso progetto)

Se vuoi eseguire due stack Docker distinti dello stesso progetto, durante `make setup` inserisci un nome istanza (es. `dev2`) quando richiesto.

Esempio:

```bash
make setup
# Nome istanza opzionale: dev2
```

Il nome viene salvato come `COMPOSE_PROJECT_NAME` in `.env`; i comandi successivi riusano automaticamente la stessa istanza:

```bash
make dev-d
make logs
make stop
```

Per cambiare istanza serve una directory/configurazione `.env` distinta; non modificare il nome in una configurazione già associata a dati senza verificarne i volumi.

### 4. Avvio successivi

Con log in primo piano:

```bash
make dev
```

In background:

```bash
make dev-d
```

### 5. Comandi utili

| Comando | Descrizione |
|--------|-------------|
| `make migrate` | Applica le migrations |
| `make makemigrations` | Crea nuove migrations |
| `make shell` | Shell Django (`manage.py shell`) |
| `make logs` | Log del web |
| `make stop` | Ferma i container (locale) |
| `make rebuild` | Ricostruisce immagini e riavvia senza cancellare i volumi |

### 6. Accesso

- **Backend API**: `http://localhost:8000`
- **Admin Django**: `http://localhost:8000/admin`

In locale il web è pubblicato solo su `127.0.0.1:8000`; PostgreSQL e Redis non pubblicano porte host. Worker, scheduler e Redis si possono avviare esplicitamente con il profilo `workers`. Per verifiche locali, eseguire `python -m unittest discover -s tests -p 'test_bootstrap.py' -v`.

Il setup verifica anche una risposta HTTP da `/admin/login/` prima di dichiarare pronto il backend. Le attese sono configurabili con `DB_WAIT_SECONDS` (default 60) e `WEB_WAIT_SECONDS` (default 30).

Per riprodurre lo stack aggiornato (Python 3.12, Node 22.22.3; Django 6.1.1, Angular 22.2.1/CLI 22.2.0, Tailwind 4.3.3):

```bash
python -m venv .venv
.venv/bin/python -m pip install -r requirements.txt -c requirements-baseline.lock
cd console && npm ci && npm run build && npm test
cd ../public_frontend && npm ci && npm run build && npm test -- --watch=false
```

La CI esegue inoltre i test bootstrap, i controlli Django e `npm audit` sui due frontend. Per la build Angular su macOS il modulo nativo della cache può interrompersi nel sandbox di Codex; il build e i test sono stati verificati fuori dal sandbox. La dipendenza `django-celery-beat` usa temporaneamente un commit upstream fissato, in attesa di una release compatibile con Django 6.1.

La modalità Keycloak è in preparazione: backend, Console e Public Frontend opzionale hanno client OIDC separati, ma il login con un realm reale non è ancora verificato. Configurazione locale, migration e gate aperti sono in [docs/engineering/keycloak-local.md](docs/engineering/keycloak-local.md). Non abilitare `AUTH_MODE=keycloak` su un'istanza esistente senza seguire quella procedura.

L'immagine Docker usa lo stesso file di vincoli Python. Il controllo `pip install` locale richiede accesso all'indice dei pacchetti; in assenza di rete la build Docker e i test nel container restano la verifica disponibile.

---

## Avvio in produzione

La configurazione di produzione non è ancora certificata per un deployment pubblico: autenticazione, credenziali, TLS e routing richiedono verifiche ulteriori. Con `SETTINGS_ENV=production`, `ALLOWED_HOSTS` deve elencare host espliciti: un valore mancante o `*` blocca l'avvio. Il check Django `--deploy` segnala ancora HSTS e redirect HTTPS, da chiudere dopo una prova del proxy e dei certificati. La build prepara gli statici e le migration sono un passaggio di preparazione separato dal processo web.

### 1. Configurare `.env`

Crea o modifica il file `.env` nella root del progetto con almeno:

```bash
SERVER_NAME=tuodominio.it
CERTBOT_EMAIL=you@example.com
SECRET_KEY=valore_casuale_non_predefinito

POSTGRES_DB=mixtumdb
POSTGRES_USER=mixtumuser
POSTGRES_PASSWORD=password_sicura
```

Per tutte le variabili disponibili fai riferimento a `.env.example` (DB, Celery, CORS, AWS S3, Slack, n8n, Twilio, ecc.).

### 2. Permessi agli script (una tantum)

Rendi eseguibili gli script richiesti da `deploy.sh`:

```bash
chmod +x scripts/deploy.sh nginx/init.sh nginx/ssl-watch.sh certbot/entrypoint.sh scripts/entrypoint.sh
```

### 3. Deploy

Solo backend (API + Nginx con SSL):

```bash
./scripts/deploy.sh
```

Per servire anche il frontend dal container Nginx:

```bash
DEPLOY_PROFILE=frontend ./scripts/deploy.sh
```

### Cosa fa `deploy.sh`

- Build e avvio dello stack in modalità PROD (`docker/docker-compose.yml` + `docker/docker-compose.prod.yml`).
- Verifica che Nginx risponda sulla porta 80 e che il webroot per ACME sia raggiungibile.
- Rilascia il certificato SSL con Certbot (one-shot) se mancante.
- Ricarica Nginx e attiva la configurazione HTTPS.
- Avvia il **loop di rinnovo automatico** Certbot.
- Esegue un `renew --dry-run` per verificare che i rinnovi funzionino.

### Accesso

**https://$SERVER_NAME**

### Comandi Docker in produzione

Per controllare servizi e log usa gli stessi file Compose del deploy:

```bash
docker compose -f docker/docker-compose.yml -f docker/docker-compose.prod.yml ps
docker compose -f docker/docker-compose.yml -f docker/docker-compose.prod.yml logs --tail=200 nginx
docker compose -f docker/docker-compose.yml -f docker/docker-compose.prod.yml logs --tail=200 certbot
```

---

## Frontend (opzionale)

### Sviluppo locale

Per lavorare sul frontend Angular in locale:

```bash
cd frontend
npm install
npm start
```

Configura l’API base nell’environment Angular su `http://localhost:8000` (o usa un proxy).

### Produzione (es. Netlify)

Configurazione tipica:

- Frontend: `https://ticket.tuodominio.it`
- Backend/API: `https://admin.tuodominio.it` (o altro sottodominio)

Nel `.env` del backend imposta CORS:

```bash
CORS_ALLOWED_ORIGINS=https://ticket.tuodominio.it
```

Nel frontend Angular imposta `apiBase` sull’URL del backend (es. `https://admin.tuodominio.it` o `https://admin.tuodominio.it/api`).

---

## Troubleshooting (produzione)

### Verificare i servizi

```bash
docker compose -f docker/docker-compose.yml -f docker/docker-compose.prod.yml ps
```

### Log Nginx e Certbot

```bash
docker compose -f docker/docker-compose.yml -f docker/docker-compose.prod.yml logs --tail=200 nginx
docker compose -f docker/docker-compose.yml -f docker/docker-compose.prod.yml logs --tail=200 certbot
```

### Test rinnovo certificato (dry-run)

```bash
docker compose -f docker/docker-compose.yml -f docker/docker-compose.prod.yml run --rm --entrypoint certbot certbot \
  renew --dry-run --webroot -w /var/www/certbot
```

### Problemi SSL comuni

- Il record DNS del dominio non punta al server.
- La porta **80** non è raggiungibile da internet (richiesta per la challenge HTTP-01).
- Con Cloudflare o altro proxy davanti al server: per la prima emissione può essere necessario usare solo DNS (no proxy) sul record.

### Errore Postgres `password authentication failed for user "mixtumuser"`

Questo errore in locale compare spesso quando il volume `postgres_data` era gia stato inizializzato con credenziali diverse rispetto al `POSTGRES_PASSWORD` attuale.

Per evitarlo tra stack paralleli, usa un `INSTANCE_NAME` diverso per ogni istanza (cosi Docker usa risorse separate). Se invece vuoi riutilizzare una stessa istanza, mantieni coerente il valore di `POSTGRES_PASSWORD` nel suo `.env`.
