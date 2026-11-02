# Keycloak locale

Questa configurazione è per sviluppo su `127.0.0.1`, non per esposizione pubblica.

## Configurazione

1. Conservare la `.env` esistente; non rieseguire setup per sostituire credenziali. Impostare `AUTH_MODE=keycloak` e le variabili `KEYCLOAK_*` mostrate in `.env.example`. Assegnare una password non vuota e unica a `KEYCLOAK_ADMIN_PASSWORD` prima di avviare il profilo `oidc`: l'esempio e Compose non forniscono più una password predefinita.
2. Il browser usa `http://127.0.0.1:8080`, che è anche l'issuer atteso dal backend. Il backend Docker legge le chiavi dal servizio interno `http://keycloak:8080`; `KEYCLOAK_ISSUER` e `KEYCLOAK_JWKS_URL` sono intenzionalmente diversi.
3. Console e Public Frontend leggono ciascuno il proprio `src/assets/mixtum-config.json` **prima** del bootstrap Angular. Contiene soltanto URL e identificativo del client pubblico, mai secret. I client Keycloak sono distinti: `mixtum-console` sulla porta 4200 e `mixtum-public` sulla porta 4300. Per un'altra istanza, sostituire i file serviti con valori propri; non pubblicare gli esempi locali su domini reali.
4. Applicare `make migrate` come passaggio esplicito. La migration `user_manager.0006_externalidentity` crea solo una tabella e una constraint; non modifica `User` e non collega account legacy.
5. Avviare PostgreSQL, backend e Keycloak con `COMPOSE_PROFILES=oidc make dev-d`; avviare la Console con `cd console && npm start` e, solo se serve, il Public Frontend con `cd public_frontend && npm start` (porta 4300). La composizione costruisce Keycloak 26.7.5 con il tema login AI 4 ISO 27001 & NIS2. Il realm canonico seleziona il tema e italiano/inglese sui volumi nuovi; su un volume esistente distribuire prima l’immagine aggiornata, poi eseguire `make keycloak-theme-apply`. Il reconciler aggiorna il nome visualizzato del realm, il tema, la localizzazione e i nomi visibili dei due client pubblici senza sostituire utenti, ID client, ruoli o flow.

Il realm contiene due client pubblici distinti, redirect URI locali ristrette, PKCE S256 e un audience mapper che inserisce `mixtum-api` negli access token. Non contiene utenti né credenziali. Creare gli utenti di prova tramite l'amministrazione Keycloak, quindi assegnare le appartenenze workspace in Mixtum. Un account Django esistente con la stessa email **non** viene collegato automaticamente: il collegamento `ExternalIdentity` richiede una procedura operativa esplicita che verifichi issuer e subject, non una ricerca per email. In `AUTH_MODE=keycloak` `/admin/` di Django non è pubblicato perché usa password locali; una UI amministrativa OIDC per questo caso non esiste ancora.

Il tema è un asset statico di Platform basato su `keycloak.v2`; Account Console, Admin Console ed email restano standard. Non dipende dal branding workspace. I tool amministrativi host-only leggono la `.env` 0600, accettano soltanto Keycloak HTTP su loopback, non seguono redirect o proxy e non passano la password amministrativa al backend. Eseguire il reconciler durante una finestra controllata, senza modifiche amministrative concorrenti al realm: l'operazione è idempotente, ma la Admin API Keycloak applica una rappresentazione del realm letta e poi aggiornata. Per un Keycloak remoto installare lo stesso tema sul server e gestire il realm tramite la procedura dell'ambiente remoto.

Il `displayName` del realm è anche il nome usato dal QR di una nuova registrazione TOTP. Verificare il QR con un utente di prova prima del rilascio. Le voci già salvate nelle app autenticatore personali non vengono rinominate automaticamente: l’utente può cambiarne l’etichetta nell’app o registrare nuovamente il fattore. Controllare separatamente i loghi caricati tramite il branding globale o di workspace e sostituire quelli che riportano ancora il vecchio wordmark.

## Contratti e sicurezza

- L'API accetta solo access token RS256 con firma, issuer, audience `mixtum-api`, `exp`, `iat`, `sub` e `typ=Bearer` validi.
- `/api/workspace/session/` restituisce utente locale e workspace accessibili. La scelta del workspace è esplicita nella Console. Le API workspace-scoped rifiutano l'header assente o un workspace non autorizzato; il server non usa più il primo workspace come fallback.
- Token e refresh token rimangono nella memoria dell'adapter Keycloak. La Console conserva in `sessionStorage` soltanto l'ID del workspace scelto, che il backend rivalida.
- Le vecchie API con JWT locale, allegati e integrazioni non sono pubblicate in `AUTH_MODE=keycloak` finché non hanno authorization e isolation adeguate. La vecchia route globale Links è stata rimossa; il nuovo plugin Links usa una API workspace-scoped disponibile in entrambe le modalità auth.

## Migration, rollout e recovery

La migration è additiva: crea una tabella nuova e indici/constraint relativi, senza backfill né rewrite della tabella utenti. Distribuire il codice compatibile, eseguire la migration una volta, configurare Keycloak e solo dopo abilitare `AUTH_MODE=keycloak`. Il rollback del codice può tornare alla modalità Django senza eliminare la tabella; **non** invertire la migration per ripristinare il login, perché ciò cancellerebbe i collegamenti espliciti. Fare backup prima di qualsiasi rollback schema. Non eseguire la migration su istanze di produzione non ancora inventariate.

Il cambio del tema non richiede migration. Per il rollback dell'immagine, impostare `loginTheme=keycloak.v2` mentre l'immagine Mixtum è ancora attiva e solo dopo distribuire l'immagine upstream; invertire l'ordine lascerebbe il realm riferito a un tema assente. Non cancellare il volume per applicare o rimuovere il tema.

## Evidenze e gate aperti

Il 2026-10-08 l'immagine Keycloak 26.7.5 personalizzata è stata costruita e ispezionata localmente. Un'istanza già popolata è stata aggiornata senza cancellare il volume: il primo reconcile ha applicato il tema, il secondo è risultato no-op; login PKCE, italiano/inglese, errore credenziali, workspace, Ticket e logout sono rimasti funzionanti. Workspace, membership e Ticket sentinella sono risultati invariati. Anche la pagina `CONFIGURE_TOTP` è stata aperta e verificata con un utente e un realm isolati, poi eliminati. Il verificatore CI ripete inoltre cambio password temporanea, OTP, due utenti/workspace isolati, upgrade di un realm con utenti/client sentinella e cold restore.

Restano fuori da questa prova routing/TLS pubblico, federation/MFA di produzione e installazione del tema su Keycloak remoti. La pipeline GitHub sul commit finale deve ancora essere osservata verde; la validazione locale non la sostituisce.
