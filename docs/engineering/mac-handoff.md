# Prova Mixtum su un secondo Mac

Questo è uno snapshot tecnico del checkout corrente, non una release pubblica. Contiene sorgenti (anche modifiche non committate), quattro wheel backend `0.1.0` e un bundle Console coordinato. Non contiene `.env`, dati, volumi, `node_modules` o credenziali. Non trasferire una vecchia istanza per questa prima prova.

Se il branch Git `codex/mixtum-handoff-2026-10-04` è disponibile, usarlo per continuare lo sviluppo sull'altro Mac: include anche il [piano consolidato](../plans/2026-10-03-stato-e-roadmap-handoff.md). L'archivio r3 resta utile per una prova isolata con wheel e bundle già costruiti; il piano consolidato è stato scritto dopo r3 e va copiato separatamente quando si usa soltanto l'archivio.

## Prerequisiti

- Mac con spazio libero sufficiente per immagini Docker, `npm ci` e database (consigliati almeno 10 GB).
- Docker Desktop avviato, Python 3.12, Node indicato da `.nvmrc` (22.22.3), npm e `make`.
- Connessione Internet per scaricare immagini, dipendenze Python e npm. I wheel Mixtum e il codice Console sono nel pacchetto; le dipendenze terze non lo sono.

## Trasferimento e verifica

Trasferisci il file unico `mac-handoff-2026-10-03-r3.tar.gz`. Da Terminale, nella directory dove l'hai salvato:

```sh
tar -xzf mac-handoff-2026-10-03-r3.tar.gz
cd mac-handoff-2026-10-03-r3
shasum -a 256 -c SHA256SUMS
tar -xzf mixtum-source.tar.gz
cd mixtum-source
```

Non usare `git clone` al posto dello snapshot: le modifiche non committate non sarebbero presenti.

## Nuova istanza locale

Scegli una directory nuova, esterna a `mixtum-source`, con nome univoco. Nell'esempio `../mixtum-smoke-mac` non deve esistere:

```sh
bash scripts/create-project.sh ../mixtum-smoke-mac
cd ../mixtum-smoke-mac
make stage-wheels WHEELHOUSE=../wheels PYTHON=python3.12
make console-build CONSOLE_BUNDLE=../mixtum-console-0.1.0.tar.gz
docker compose --env-file .env config --quiet
make prepare
make up
```

I percorsi del wheelhouse e del bundle sopra assumono che `mixtum-smoke-mac`, `mixtum-source` e `wheels` siano nella stessa directory di handoff. Se scegli un'altra posizione, passa percorsi assoluti. `make stage-wheels` precede Docker; `make console-build` scarica le dipendenze npm e potrebbe richiedere tempo. `make prepare` migra solo il database del nuovo progetto, non quello di un'istanza esistente. Non usare `down -v` per risolvere eventuali errori.

Apri `http://127.0.0.1:4200`, controlla `http://127.0.0.1:8000/health/live/` e `http://127.0.0.1:8000/health/ready/`. Per creare il primo utente e workspace segui [la guida d'istanza](../../templates/instance/README.md), sezione finale: il login Keycloak e la selezione workspace sono parte della prova, non già verificati da un health check. `make stop` arresta senza rimuovere i volumi.

## Se qualcosa non parte

Conserva l'output dei comandi falliti, la prima eccezione e lo stato dei servizi:

```sh
docker compose --env-file .env ps
docker compose --env-file .env logs --tail=150 web console keycloak db
```

Prima di condividere i log, oscura password, token, cookie e dati personali. Non condividere `.env`. Segna il primo comando fallito, la versione di Docker/Python/Node, lo spazio libero e se gli endpoint live/ready rispondono. La configurazione Keycloak è locale e vincolata a loopback; questa procedura non va esposta su Internet.
