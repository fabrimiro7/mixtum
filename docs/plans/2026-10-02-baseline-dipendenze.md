# ExecPlan — Chiusura setup e baseline dipendenze

## 1. Goal

Il setup locale dichiara pronto il web solo dopo una risposta HTTP. Backend, Console e Public Frontend dispongono di una baseline di dipendenze e di comandi di verifica ripetibili.

## 2. Non-goals

Nessun upgrade di Django, Angular o Tailwind; nessuna modifica a schema, auth, workspace, plugin o Ticket.

## 3. Current state

Il setup interpretava qualsiasi errore di `docker volume inspect` come assenza del volume e dichiarava successo dopo `compose up`. I frontend avevano lockfile installabili ma test starter incompatibili con lo shell attuale. I requisiti Python includevano intervalli aperti.

## 4. Target architecture

Resta un solo setup Compose. Il controllo volume usa una lista con esito verificato; dopo l'avvio del web, il setup interroga `/admin/login/` nel container con timeout. Il backend usa un file di vincoli Python; ogni frontend resta installato dal proprio `package-lock.json`.

## 5. Security impact

Un errore Docker nella lettura dei volumi interrompe il setup prima di creare `.env`. Il controllo HTTP resta interno al container e non espone nuove porte. Nessuna modifica ad autenticazione, autorizzazione o isolamento workspace.

## 6. Data/migration impact

Nessuna nuova migration. I test Django usano un database di test creato sul solo PostgreSQL A3 dedicato.

## 7. Deployment impact

Il Dockerfile usa un digest fissato per Python 3.12 slim e installa le dipendenze con `requirements-baseline.lock` come constraints. Gli strumenti apt e i pacchetti di sistema non sono ancora bloccati a una fotografia completa; rivalutare prima della release pubblica.

## 8. Milestones

- Setup: distinguere errore Docker da volume assente e verificare HTTP prima del messaggio di successo.
- Dipendenze: installare con `npm ci`, registrare le versioni Python risolte in Docker e fissarle come constraints.
- Verifica: build e test dei tre componenti, poi documentare limiti reali.

## 9. Test plan e risultati

- `python -m unittest discover -s tests -p 'test_bootstrap.py' -v`: 10 test superati, inclusi errore lista volumi e timeout HTTP.
- Immagine backend ricostruita con constraints; `pip check` superato. Nel progetto isolato `mixtum-a3-20261002`, `/admin/login/` ha risposto HTTP 200; `python manage.py test` ha eseguito 31 test con esito positivo. La suite backend comprende però 15 test vuoti e non prova ancora la sicurezza workspace.
- `npm ci --no-audit --no-fund` e `npm run build` superati per Console e Public Frontend. `npm test -- --watch=false --browsers=ChromeHeadless`: 2 test superati per ciascuno dopo aver corretto gli spec starter. TypeScript `--noEmit` superato per entrambi.
- Versioni risolte in entrambi i frontend: Angular 18.2.13, CLI 18.2.19, Tailwind 3.4.17, TypeScript 5.5.4; host Node 22.22.3 e npm 10.9.8.
- L'installazione pip in `.venv` locale è stata bloccata dalla risoluzione DNS dell'indice; l'immagine Docker ha fornito l'ambiente Python isolato. Le build Angular nel sandbox si interrompevano con codice 134; fuori dal sandbox entrambe sono riuscite.

## 10. Rollout

Nessun rollout pubblico. I container A3 sono stati fermati; il volume dedicato resta disponibile per ispezione. La baseline è il punto di confronto per i futuri upgrade separati.

## 11. Removal plan

Rimossi dagli spec Angular i controlli del titolo dello starter che non appartiene al componente. Nessun codice applicativo sostituito.

## 12. Completion criteria

Setup fail-safe e HTTP verificati, installazioni e build ripetibili, test eseguiti e limiti annotati. Prima della release servono test auth/workspace, revisione delle dipendenze e verifica completa di TLS e routing.
