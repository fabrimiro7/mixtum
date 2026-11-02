# Prodotti, AI Labs, visibilità Console e aggiornamenti cliente

Stato: piano operativo, non implementazione completata. Decisioni di organizzazione concordate nella conversazione dell'8 ottobre 2026; dettagli operativi proposti sotto. Nessun repository remoto, pacchetto o deploy viene creato da questo documento.

## 1. Goal

Usare Mixtum come base comune con AI Labs integrato nella Platform e nella Console. Distribuire i prodotti da repository separati e combinarli in istanze cliente versionate. Nascondere singoli prodotti dal menu mantenendoli disponibili alle integrazioni autorizzate. Trasferire i fix Mixtum alle istanze aggiornando dipendenze e artefatti, senza fork o copia manuale del Core.

Prova conclusiva: due istanze con composizioni e menu differenti; aggiornare una sola istanza con un fix Platform, conservando dati, configurazioni, branding ed extension, e dimostrare che l'altra conserva la versione precedente.

## 2. Non-goals

- Non sviluppare contemporaneamente i sette prodotti né estrarli automaticamente in microservizi.
- Non installare pacchetti a caldo dalla Console e non eseguire aggiornamenti automatici sui clienti.
- Non confondere un flag del menu con una revoca di accesso o una disabilitazione del backend.
- Non costruire un servizio generale di feature flag, marketplace o gestione licenze.
- Pubblicazione su registry, push, deploy pubblico e creazione di repository remoti restano attività operative successive.

## 3. Current state

- `pyproject.toml` costruisce `mixtum-platform-backend==0.1.0`, contenente `mixtum_core` e `base_modules`, senza i plugin.
- Ticket, Links ed extension hanno già pacchetti separati ma risiedono nello stesso repository. Il percorso di plugin esterni è disponibile.
- `templates/instance/requirements.txt` fissa Platform e Ticket a versioni esatte. `scripts/create-project.sh` copia il lock Python come `constraints.txt` e genera un'istanza separata.
- `mixtum_core/plugin_registry.py` verifica manifest, dipendenze e `platform_api`; la compatibilità attuale è un confronto esatto con `0.1`, non un risolutore di intervalli di versioni.
- `mixtum_instance/composition.json` seleziona plugin, extension e capability. Il backend registra solo i plugin abilitati; la Console seleziona i relativi contributi durante la build.
- `packages/console-api/src/index.ts` espone route e navigazione. La sidebar aggrega le voci e applica il controllo amministrativo disponibile; non esiste ancora un flag dinamico di visibilità del prodotto.
- La sessione in `base_modules/workspace/views.py` espone membership e capacità amministrative derivate dal backend. Non duplicare questo confine.
- Makefile, Dockerfile, tool, configurazione frontend e directory Keycloak vengono copiati nell'istanza. Un aggiornamento del solo wheel NON aggiorna questi file.
- Snapshot, restore e upgrade hanno prove locali registrate in `2026-10-04-prosecuzione-v01.md`. La CI GitHub sul codice finale del tema Keycloak è ancora un gate aperto.
- I sorgenti esterni Documents e degli altri prodotti non sono stati ancora forniti/esaminati. Il loro riuso va valutato prima di definire nuove primitive AI.

## 4. Target architecture

### Repository e ownership

| Repository proposto | Responsabilità |
|---|---|
| `mixtum` | Core, Platform con AI Labs, Console, contratti pubblici, template, generatori e verificatori |
| `mixtum-ticket`, `mixtum-documents`, `mixtum-observatory`, `mixtum-woocommerce`, `mixtum-academy`, `mixtum-events` | Backend, contributi Console, migration, test e release del singolo prodotto |
| Repository di istanza cliente/progetto | Versioni esatte, composizione, configurazioni non segrete, branding di distribuzione, extension, eventuale Public Frontend e deploy |

AI Labs è un unico componente di Platform: agenti/flow, tool, ingestion, RAG e gestione esecuzioni, con UI nella Console e API pubbliche. I verticali registrano strumenti e utilizzano contratti pubblici; AI Labs non importa internals dei verticali. La direzione resta Extension -> Plugin -> Platform -> Core. Qdrant e provider LLM sono adapter della Platform. Un repository separato non implica un processo o database separato.

Ogni prodotto rilascia wheel backend e tarball Angular coordinati, dichiarando la compatibilità con Platform e Console API. L'istanza blocca le versioni risolte; un plugin o un'extension incompatibile blocca l'upgrade. Durante la fase 0.x la compatibilità deve essere documentata e provata, non dedotta dal numero della release.

### Tre scelte distinte per i prodotti

| Scelta | Effetto |
|---|---|
| Installato e abilitato nella composizione | Backend e contributi Console disponibili; modifiche richiedono preparazione/build/deploy |
| Visibile nel menu | Preferenza di navigazione modificabile a runtime, senza rimuovere API, tool, job o dati |
| Autorizzato per l'attore | Permessi backend su workspace, risorse e azioni; vale anche per API, agenti e accesso diretto |

Prima implementazione proposta: flag tipizzato `menu_visible` per ID di prodotto, default d'istanza e override per workspace. L'amministratore centrale gestisce il default; il gestore può modificare l'override del proprio workspace usando i controlli amministrativi esistenti. Nessun override può installare/abilitare un prodotto o concedere permessi. Per i prodotti attualmente abilitati, l'assenza di una preferenza mantiene il menu visibile, soggetto ai controlli esistenti.

Il menu effettivo combina composizione disponibile, preferenza risolta e capacità dell'utente per la voce. Nascondere Documents permette di continuare a utilizzarlo da AI Labs o tramite URL/API se autorizzati. Se serve negare l'utilizzo, si usano i permessi; una futura abilitazione funzionale per workspace richiederà un contratto separato, verificato anche per job e tool.

Estendere i contributi pubblici e la sessione/configurazione autorizzata esistenti, conservando l'ID del prodotto quando si aggregano le voci. Non introdurre un secondo registry o un elenco hardcoded di prodotti nella sidebar. Al cambio workspace/logout eliminare le preferenze precedenti; in assenza di configurazione valida non riutilizzare lo stato di un altro workspace. La UI amministrativa resta raggiungibile indipendentemente dai flag dei prodotti. Le modifiche aggiornano subito la sessione corrente; le altre sessioni riallineano la navigazione al successivo refresh della configurazione, senza promessa di push in tempo reale.

### Come un fix arriva al cliente

1. Correggere il sorgente nel repository Mixtum, testare e produrre una nuova release immutabile. Esempio illustrativo: `0.1.0` -> `0.1.1`; non sovrascrivere artefatti già distribuiti con lo stesso numero.
2. Preparare wheel Platform, bundle Console e componenti infrastrutturali/template pertinenti con versioni, checksum, note di compatibilità e istruzioni di migration. Un fix solo backend può lasciare invariati gli altri artefatti se la compatibilità è provata.
3. Nel repository cliente preparare un aggiornamento reviewabile di `requirements.txt`, vincoli, dipendenze Console/lock e riferimenti agli artefatti interessati. I prodotti possono conservare la propria versione se compatibile.
4. Costruire un ambiente pulito dalle nuove dipendenze e una composizione staging corrispondente al cliente. Verificare plugin ed extension, migration e percorsi critici.
5. Eseguire backup coerente e deploy della composizione verificata con i comandi d'istanza esistenti. Registrare le versioni effettivamente distribuite.

Il cliente non possiede una copia sorgente modificabile del Core: il container installa il wheel scelto. Le modifiche specifiche vivono nelle extension e rimangono indipendenti dal pacchetto aggiornato. Se un'extension dipende da un contratto cambiato, si adatta e testa prima del deploy.

### File generati e aggiornamento del template

Versionare la provenienza del template e l'inventario/checksum dei file generati insieme agli artefatti; riusare gli inventari esistenti ove sufficienti. Preparare un confronto tra template originale, nuovo template e file cliente. Applicare automaticamente soltanto cambiamenti non conflittuali nell'ambito di un aggiornamento richiesto; presentare i conflitti per risoluzione esplicita. Non rieseguire il generatore su una directory popolata.

Preservare `.env`, composizione, registrazioni plugin, branding, extension, redirect/issuer specifici, segreti e volumi. Anche la directory Keycloak richiede distinzione tra asset standard e realm personalizzato: sostituire il JSON canonico non aggiorna un realm esistente e può perdere configurazioni locali nel file. Usare riconciliazioni limitate ai campi gestiti, come già avviene per il tema.

Distribuzione iniziale degli artefatti tramite insiemi locali con checksum, già supportati. Registry privati Python/npm/container possono automatizzare il trasporto in seguito; non sono una precondizione per provare l'upgrade. Segreti, database e snapshot non entrano nel repository cliente.

## 5. Security impact

Il flag menu è UX, mai authorization. Mutazioni della preferenza devono validare ID registrato, attore, workspace e campi ammessi e produrre audit senza segreti. Testare membro, gestore, amministratore, workspace estraneo e tentativi di escalation. Nascondere una voce non amplia né riduce i permessi effettivi.

AI Labs applica permessi e ambito prima del retrieval e prima dei tool con effetti; la semplice associazione di un agente a un prodotto non concede accesso. Riutilizzare le primitive di dominio dei prodotti. Dipendenze e artefatti sono codice attendibile da verificare, non upload eseguibili accettati liberamente dalla Console.

## 6. Data/migration impact

Questa consegna documentale non modifica schema o dati. L'implementazione delle preferenze potrà richiedere una migration additiva dopo verifica delle primitive disponibili; usare ID stabili dei prodotti, senza FK Core -> modelli plugin. Non inventare backfill di autorizzazioni. Le preferenze runtime risiedono nel database e devono sopravvivere a upgrade e restore.

Nell'estrazione dei prodotti preservare ID manifest, app label Django, tabelle, nomi delle migration e contratti pubblici ove possibile. Ogni cambio necessario richiede un piano esplicito. Non eseguire migrazioni inverse per disabilitare un prodotto. Per downgrade incompatibili ripristinare l'insieme coerente di dati, media, credenziali, configurazione e artefatti.

## 7. Deployment impact

I repository separati producono pacchetti caricati nello stesso backend e nella stessa Console. L'aggiunta di pacchetti richiede build/deploy; il cambio di visibilità non richiede rebuild. I fix entrano nei container dopo ricostruzione e ricreazione, non al semplice cambio del file requirements.

Nessun servizio AI viene avviato da questo piano. Le dipendenze operative di AI Labs verranno determinate dai primi percorsi reali e dai sorgenti esistenti. Gli aggiornamenti iniziali usano una finestra di manutenzione con snapshot cold; zero downtime non è un requisito implicito.

## 8. Milestones

| Gate | Operazione e file principali | Accettazione e prove |
|---|---|---|
| M0 | Consolidare baseline v0.1 e tema; piani di stato, CI e artefatti | CI Linux osservata sul commit finale e insieme di artefatti identificabile; distinguere verifiche locali da CI |
| M1 | Implementare preferenze menu; workspace/sessione, Console API, sidebar e amministrazione | Due prodotti coesistono; nasconderne uno non interrompe API/tool autorizzati; cambio workspace e permessi verificati; audit e restore preferenze |
| M2 | Versionamento release e aggiornamento istanze; packaging, template e tool esistenti | Upgrade di un fix Platform da una versione alla successiva su una delle due istanze; l'altra invariata; conflitti template visibili; extension, dati e flag preservati; rollback provato |
| M3 | Inventario del Documents esistente e primo prodotto esterno reale; successiva estrazione Ticket | Sorgenti esaminati; separazione dominio/capability; wheel/tarball installabili senza checkout; storia migration preservata; Console senza import obbligatori di prodotti assenti |
| M4 | AI Labs minimo in Mixtum e strumenti dei prodotti | Un agente/flow con fonte indicizzata, UI/API ed esecuzione da un prodotto; secondo consumatore riusa il motore; permessi, revoche e RAG verificati |
| M5 | Ripetere lo schema per gli altri prodotti | Per ogni prodotto: primo percorso utile, dipendenze esplicite, test e release; priorità commerciale da definire |

M1 e M2 definiscono il primo blocco di implementazione dopo la baseline. L'inventario dei sorgenti esterni può iniziare appena disponibili; deve precedere la progettazione dettagliata di M4. Non creare in anticipo sei repository vuoti senza un prodotto da migrare o costruire.

## 9. Test plan

- Menu: prodotto abilitato/assente, default e override, due workspace, membro/gestore/admin, URL diretto autorizzato e negato, aggiornamento preferenze, logout e configurazione non disponibile.
- Upgrade: due versioni effettivamente differenti e fix osservabile, build pulita, compatibilità prodotti/extension, migrazioni PostgreSQL, custom template conflittuale, dati e flag sentinella, restore e rollback coerente.
- Estrazione: installazione wheel/tarball senza sorgenti, nessun import del prodotto dal Core/Console condivisa, app label e migration stabili, disabilitazione con conservazione dati.
- AI Labs: matrici autorizzative e prove RAG/tool definite in `SECURITY.md` e `TESTING.md`, su almeno due consumatori.

Riutilizzare i comandi esistenti per i gate pertinenti:

```sh
python3.12 -m unittest discover -s tests -p 'test_*.py' -q
npm test --prefix console
npm run build --prefix console
```

Per PostgreSQL e Keycloak reali usare la pipeline e il flusso locale documentati; non simulare GitHub Actions sul Mac. Nell'istanza riutilizzare `make install-wheels`, `make wheel-check`, `make stage-wheels`, `make console-build`, `make snapshot-volumes`, `make prepare`, `make up`, `make restore-volumes` con gli argomenti documentati. Non esiste ancora un comando universale `make upgrade`: eventuale nuova automazione deve orchestrare questi passaggi, non duplicarli.

## 10. Rollout

Prima prova su istanze dedicate e composizioni piccole. Estrarre un prodotto alla volta. Ogni aggiornamento cliente parte da versioni esatte, compatibilità verificata e piano di recovery. Un controllo fallito interrompe la progressione al gate successivo. Rilasciare la visibilità con default compatibili prima di introdurre override. Promuovere in produzione soltanto dopo il relativo gate operativo; non usare la demo temporanea come istanza cliente definitiva.

## 11. Removal plan

Quando un prodotto è estratto e verificato, aggiornare generatori, import Console, fixture e CI a consumare i suoi artefatti. Rimuovere la copia sorgente nel Framework soltanto quando tutti i consumer sono migrati, mantenendo invariata la storia delle migration. Non mantenere due implementazioni dello stesso prodotto. Conservare nel Framework solo fixture/esempi tecnici dichiarati come tali.

## 12. Completion criteria

- Documentazione e release distinguono Platform con AI Labs, prodotti e istanze.
- Menu configurabile senza rebuild e senza alterare i permessi o la composizione installata.
- Un fix Mixtum raggiunge una specifica istanza tramite upgrade ripetibile, senza modificare l'altra.
- Personalizzazioni, flag, dati e identità sono conservati; conflitti e incompatibilità impediscono aggiornamenti silenziosi.
- Prodotto esterno reale e AI Labs rispettano i contratti e la direzione delle dipendenze.
- Test e recovery pertinenti passano e sono registrati secondo `DEFINITION_OF_DONE.md`.

## Evidenze di pianificazione

2026-10-08: letti registry, contratto Console, sidebar, sessione workspace, generatore, template e procedure di release. Confermati packaging versionato esistente e assenza del flag dinamico menu. Individuato il limite dell'aggiornamento del solo wheel sui file copiati dal template. Nessuna modifica applicativa, migration o deploy eseguita in questa fase.
