# Mixtum v0.1 locale/staging

Questa consegna è una baseline installabile e verificata per Mac e CI Linux. Non è una pubblicazione di pacchetti, un deploy pubblico o una garanzia Kubernetes.

## Artefatti coordinati

Conservare nello stesso insieme:

- wheel Platform e dei plugin/extension abilitati;
- bundle Console e, se usato, bundle Public Frontend;
- directory istanza completa, inclusi composizione, lock, realm e `.env` protetto;
- snapshot cold di PostgreSQL, Keycloak e media;
- `SHA256SUMS` dell'insieme.

Verificare sempre i checksum prima dell'installazione o del restore. Non mescolare database o realm di uno snapshot con password, wheel o configurazione di un altro checkpoint.

## Installazione e avvio

Usare Python 3.12, Node 22.22.3, npm e Docker. Da una directory istanza nuova:

```sh
make install-wheels WHEELHOUSE=/percorso/wheels PYTHON=python3.12
make check
make wheel-check
make stage-wheels WHEELHOUSE=/percorso/wheels PYTHON=python3.12
make console-build CONSOLE_BUNDLE=/percorso/mixtum-console-0.1.0.tar.gz
make prepare
make up
```

`make prepare` applica migration soltanto al database indicato dall'istanza. Verificare live/readiness, discovery OIDC e login reale prima di considerare concluso l'avvio. Arrestare senza cancellare dati con `make stop`.

## Bootstrap amministrativo

Creare gli account in Keycloak e completare almeno una sessione, così che l'identità `(issuer, subject)` sia verificata localmente. Abilitare il primo amministratore centrale con:

```sh
docker compose --env-file .env run --rm web \
  python manage.py grant_platform_admin --issuer ISSUER --subject SUBJECT
```

Il comando imposta solo `is_superuser`: non crea password Django, non usa email come identità e non assegna automaticamente accesso Ticket. Workspace, gestore iniziale, membership e branding sono poi amministrabili dalla Console.

## Aggiornamento

1. Fermare l'istanza e creare uno snapshot cold.
2. Conservare l'intero insieme baseline, inclusi `.env`, composizione e artefatti.
3. Sostituire wheel e bundle con l'insieme finale coordinato.
4. Eseguire `make prepare`, quindi `make up`.
5. Verificare login, membership, Ticket, branding, media e `python manage.py migrate --check` nel container web.

Non effettuare il downgrade del solo codice dopo migration non reversibili. Il rollback supportato è il ripristino dell'insieme coerente precedente.

## Recovery coerente

Da una seconda directory istanza, copiata dal checkpoint dello snapshot, cambiare soltanto `COMPOSE_PROJECT_NAME`. A servizi fermi e senza volumi preesistenti:

```sh
make restore-volumes SNAPSHOT_DIR=/percorso/snapshot
make up
```

Il restore non applica migration. Prima dell'avvio confermare versioni e credenziali; dopo l'avvio provare login browser, membership, Ticket, branding e media. Gli snapshot contengono dati sensibili e vanno protetti come il database.

## Combinazioni verificate

- Platform + Ticket + Console, con Keycloak e PostgreSQL.
- Platform + Ticket + Links + `demo_support`, con branding distinto.
- Public Frontend opzionale con client OIDC `mixtum-public` separato.
- Media branding locale limitato a immagini validate; gli allegati non vengono esposti dalla route locale.

Non sono dichiarati disponibili in questa baseline S3, AI/RAG, Documents, configuratore visuale, Kubernetes, commenti/SLA/notifiche Ticket o altre combinazioni di servizi non provate.

## Evidenze richieste

La chiusura richiede suite repository e Django su PostgreSQL, build/test browser Console e Public, prove autorizzative e cross-workspace, wheel/plugin esterno, immagine Docker, restore e upgrade. La pipeline GitHub deve essere osservata sul commit finale: la sola validazione del file YAML non sostituisce questo gate.
