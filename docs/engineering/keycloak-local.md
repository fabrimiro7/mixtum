# Keycloak locale — consegna 2 in corso

Questa configurazione è per sviluppo su `127.0.0.1`, non per esposizione pubblica.

## Configurazione

1. Conservare la `.env` esistente; non rieseguire setup per sostituire credenziali. Impostare `AUTH_MODE=keycloak` e le variabili `KEYCLOAK_*` mostrate in `.env.example`. Assegnare una password non vuota e unica a `KEYCLOAK_ADMIN_PASSWORD` prima di avviare il profilo `oidc`: l'esempio e Compose non forniscono più una password predefinita.
2. Il browser usa `http://127.0.0.1:8080`, che è anche l'issuer atteso dal backend. Il backend Docker legge le chiavi dal servizio interno `http://keycloak:8080`; `KEYCLOAK_ISSUER` e `KEYCLOAK_JWKS_URL` sono intenzionalmente diversi.
3. Console e Public Frontend leggono ciascuno il proprio `src/assets/mixtum-config.json` **prima** del bootstrap Angular. Contiene soltanto URL e identificativo del client pubblico, mai secret. I client Keycloak sono distinti: `mixtum-console` sulla porta 4200 e `mixtum-public` sulla porta 4300. Per un'altra istanza, sostituire i file serviti con valori propri; non pubblicare gli esempi locali su domini reali.
4. Applicare `make migrate` come passaggio esplicito. La migration `user_manager.0006_externalidentity` crea solo una tabella e una constraint; non modifica `User` e non collega account legacy.
5. Avviare PostgreSQL, backend e Keycloak con `COMPOSE_PROFILES=oidc make dev-d`; avviare la Console con `cd console && npm start` e, solo se serve, il Public Frontend con `cd public_frontend && npm start` (porta 4300). Il profilo Keycloak importa `docker/keycloak/realm-mixtum.json` soltanto se il realm non esiste già nel suo volume: per volumi preesistenti il secondo client va aggiunto esplicitamente tramite amministrazione, senza cancellare il volume.

Il realm contiene due client pubblici distinti, redirect URI locali ristrette, PKCE S256 e un audience mapper che inserisce `mixtum-api` negli access token. Non contiene utenti né credenziali. Creare gli utenti di prova tramite l'amministrazione Keycloak, quindi assegnare le appartenenze workspace in Mixtum. Un account Django esistente con la stessa email **non** viene collegato automaticamente: il collegamento `ExternalIdentity` richiede una procedura operativa esplicita che verifichi issuer e subject, non una ricerca per email. In `AUTH_MODE=keycloak` `/admin/` di Django non è pubblicato perché usa password locali; una UI amministrativa OIDC per questo caso non esiste ancora.

## Contratti e sicurezza

- L'API accetta solo access token RS256 con firma, issuer, audience `mixtum-api`, `exp`, `iat`, `sub` e `typ=Bearer` validi.
- `/api/workspace/session/` restituisce utente locale e workspace accessibili. La scelta del workspace è esplicita nella Console. Le API workspace-scoped rifiutano l'header assente o un workspace non autorizzato; il server non usa più il primo workspace come fallback.
- Token e refresh token rimangono nella memoria dell'adapter Keycloak. La Console conserva in `sessionStorage` soltanto l'ID del workspace scelto, che il backend rivalida.
- Le vecchie API con JWT locale, allegati e integrazioni non sono pubblicate in `AUTH_MODE=keycloak` finché non hanno authorization e isolation adeguate. La vecchia route globale Links è stata rimossa; il nuovo plugin Links usa una API workspace-scoped disponibile in entrambe le modalità auth.

## Migration, rollout e recovery

La migration è additiva: crea una tabella nuova e indici/constraint relativi, senza backfill né rewrite della tabella utenti. Distribuire il codice compatibile, eseguire la migration una volta, configurare Keycloak e solo dopo abilitare `AUTH_MODE=keycloak`. Il rollback del codice può tornare alla modalità Django senza eliminare la tabella; **non** invertire la migration per ripristinare il login, perché ciò cancellerebbe i collegamenti espliciti. Fare backup prima di qualsiasi rollback schema. Non eseguire la migration su istanze di produzione non ancora inventariate.

## Gate ancora aperti

Il daemon Docker è tornato raggiungibile il 2026-10-03, ma la prima prova isolata non ha potuto creare i container per un errore di I/O nei metadati Docker con il disco host al 100%; dettagli e risorse temporanee rimaste sono nel [piano di release](../plans/2026-10-02-platform-v01.md). Non sono ancora verificati import reale del realm, login browser end-to-end dei due client, refresh/logout, due utenti reali e due workspace su PostgreSQL, né routing/TLS di produzione. Il Public Frontend è stato portato al client OIDC separato, ma non va dichiarato pronto per `AUTH_MODE=keycloak` prima di queste prove. Il test automatico usa token firmati localmente e chiavi JWKS simulate; non sostituisce la prova con Keycloak reale.
