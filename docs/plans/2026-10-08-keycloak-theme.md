# Tema Keycloak Mixtum nel Framework

## 1. Goal

Le composizioni locali e le istanze generate costruiscono Keycloak 26.7.5 con il tema login Mixtum di `mixtum-iso`. Le istanze nuove lo importano dal realm canonico; quelle esistenti lo selezionano con un reconciler idempotente senza perdere utenti o configurazioni.

## 2. Non-goals

- Nessuna modifica a Console, API, authorization o workspace isolation.
- Nessun flow LoA2, ruolo, gruppo o client importato da ISO.
- Nessun tema custom per Account Console, Admin Console o email.
- Nessuna policy MFA nuova e nessun branding Keycloak dinamico per workspace.

## 3. Current state

Il realm canonico contiene i due client pubblici PKCE ma non configura tema o localizzazione. Le composizioni usano direttamente l'immagine upstream. Il generatore copia solo il JSON del realm. Il provisioner utenti possiede già i controlli locali e di secret richiesti per un client Admin API.

## 4. Target architecture

Il tema è infrastruttura Platform sotto `docker/keycloak`, copiato integralmente nelle istanze generate e incluso in un'immagine derivata dalla release Keycloak fissata. Un helper Admin API condiviso dai tool host mantiene un solo confine per configurazione, credenziali, redirect, proxy e timeout. Il reconciler gestisce soltanto display name, login theme e localizzazione.

La direzione Extension -> Plugin -> Platform -> Core non cambia; Core e plugin non dipendono da Keycloak o dagli asset del tema.

## 5. Security impact

Le credenziali amministrative restano nel `.env` locale 0600 e nel processo host, non nel container web. I tool accettano solo HTTP loopback, disabilitano proxy e redirect, limitano le risposte e non stampano token/password. Il reconciler verifica che il tema sia installato prima di mutare il realm e preserva i campi non gestiti.

## 6. Data/migration impact

Nessuna migration Django/PostgreSQL. Per Keycloak la modifica è una PUT idempotente della rappresentazione del realm dopo una GET; utenti, client, ruoli, flow e attributi esistenti rimangono nella rappresentazione inviata.

## 7. Deployment impact

Keycloak passa dall'immagine upstream alla build locale derivata da `quay.io/keycloak/keycloak:26.7.5`. `make prepare` costruisce anche Keycloak, attende la readiness e applica il tema prima delle migration. Per il rollback si seleziona prima `keycloak.v2`, poi si può tornare all'immagine upstream.

## 8. Milestones

1. Portare tema, font, logo, favicon e licenza; aggiornare realm, compose e generatore. Gate: test statici e build immagine.
2. Estrarre il client Admin API e aggiungere reconciler/Make target. Gate: test unitari di sicurezza, merge e idempotenza.
3. Estendere la verifica browser/staging e documentare upgrade/rollback. Gate: suite repository, Compose reale e controllo visuale Keycloak.

## 9. Test plan

- Test realm, asset e copia esatta nell'istanza generata.
- Test del reconciler: apply, no-op, tema assente, realm assente, URL/file insicuri, campi sentinella preservati e segreti assenti dai log.
- Build dell'immagine e verifica dei file interni.
- Playwright: PKCE, tema/font/logo/colore, lingua italiana/inglese, errore login, cambio password e logout.
- Regressione della prova PostgreSQL/Keycloak reale, isolamento workspace e cold restore.

## 10. Rollout

Costruire l'immagine, avviare Keycloak, attendere readiness, eseguire il reconciler due volte e verificare che la seconda sia no-op; solo dopo avviare l'applicazione. Per Keycloak esterno installare prima lo stesso tema sul server e configurare il realm fuori dal tool locale.

## 11. Removal plan

La logica Admin API duplicata nel provisioner utenti viene rimossa e sostituita dall'helper condiviso. Il riferimento diretto all'immagine upstream nelle composizioni viene sostituito dalla build locale.

## 12. Completion criteria

Tema visibile e verificato su istanza nuova e preesistente; dati Keycloak preservati; test pertinenti verdi; documentazione di installazione e rollback aggiornata; nessun secret esposto e nessun cambiamento ai contratti applicativi.

## Evidenze di completamento

- Porting ISO verificato byte-per-byte per CSS, font, logo, favicon e licenza; immagine derivata da Keycloak 26.7.5 fissata anche per digest.
- Reconciler provato su realm nuovo e su volume esistente: apply seguito da no-op, con workspace, membership, utente e Ticket conservati.
- Playwright reale: logo/font/colore, italiano/inglese, errore credenziali, PKCE, workspace, Ticket, logout e pagina OTP. Il cambio password temporanea è incluso nello staging CI.
- PASS locali: 84 test repository, 181 test Django, 23 test browser Console, build Console, build/ispezione immagine Keycloak, `npm audit` con zero vulnerabilità e `git diff --check`.
- Gate esterno residuo: osservare la pipeline GitHub del commit finale. Nessuna migration Django/PostgreSQL.
