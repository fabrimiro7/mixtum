# Mixtum AI Labs e Documents — ExecPlan

## 1. Goal

Realizzare AI Labs come capability Platform con Console e API riusabili, e Documents come prodotto installabile. Lo stesso runtime deve eseguire un flow dalla Console, da Documents e da Ticket con autorizzazione workspace, budget e traccia gerarchica.

## 2. Non-goals

- Nessuna migrazione di database legacy.
- Nessuna esecuzione di codice arbitrario scritto nella Console.
- Ollama, vLLM, connettori ISO simulati e aggiornamenti automatici restano successivi.
- Nessuna funzione fiscale o cliente-specifica entra nella Platform.

## 3. Current state

Mixtum dispone ora di un primo runtime AI condiviso e di un package Documents selezionabile. Provider, modelli, agenti e flow versionati, budget, trace, approvazioni, knowledge base, adapter Qdrant e i contratti tool/source sono implementati. Restano da chiudere i gate reali Regolo/Qdrant, i nodi avanzati e la chat Documents con citazioni.

La matrice di provenienza e parità è in `docs/engineering/ai-labs-source-inventory.md`.

## 4. Target architecture

`base_modules.ai_labs` possiede provider astratti, agenti, flow versionati, esecuzioni, tool registry, approvazioni, tracing, budget e knowledge base. Qdrant e provider LLM sono adapter. I prodotti registrano nodi, tool e resource adapter tramite contratti pubblici.

Documents è un prodotto separatamente pacchettizzato e dipende solo dalla Platform. Possiede documenti, versioni, cartelle, tassonomie, ACL e risultati; usa AI Labs per esecuzione, ingestion e retrieval. Ticket registra un tool minimo tramite il contratto Platform. Direzione: Extension -> Plugin -> Platform -> Core.

API principali: gestione provider/modelli, agenti, flow e versioni; avvio idempotente e lettura run/eventi/consumi; annullamento; approvazione/rifiuto con ripresa; knowledge base, sorgenti, ingestion e ricerca. Gli endpoint workspace-scoped usano `X-Workspace-Id` e scope server-side.

## 5. Security impact

Il modello non concede accesso. Ogni tool dichiara schema, permesso, scope, side effect e policy di approvazione. Il runtime rivalida attore, workspace e target prima di retrieval/tool e alla ripresa. Endpoint esterni sono configurati centralmente, con blocco SSRF; secret referenziati tramite variabili host. Prompt, output e contenuti RAG sono non fidati. Le tracce predefinite escludono segreti, immagini e contenuti; debug è autorizzato e scade.

## 6. Data/migration impact

Migration additive per le nuove tabelle AI Labs e Documents. Nessun backfill e nessun servizio esterno in migration. Indici sulle chiavi di scope, stato, tempo e idempotenza. Rollback del codice richiede ripristino coerente se le nuove funzioni sono già usate; disabilitare Documents conserva tabelle e file.

## 7. Deployment impact

Redis/Celery sono obbligatori quando AI Labs esegue job. Qdrant è richiesto solo con capability RAG. Regolo/OpenAI-compatible usano secret host-side. Compose espone Redis/Qdrant solo internamente e aggiunge healthcheck e volumi. Migration eseguite dal target `prepare`, non dai worker.

## 8. Milestones

| Gate | Risultato | Prova |
|---|---|---|
| P0 | Inventario, fixture e contratti | Matrice sorgenti/test e baseline verde |
| P1 | Provider, run, trace e budget | Chiamata fake e adapter HTTP; concorrenza budget; isolamento |
| P2 | Documents e PDF | Wheel separato; documento intero/area; errori espliciti |
| P3 | Knowledge/RAG | Revisioni, Qdrant, filtri, delete/reindex, citazioni |
| P4 | Grafo/agent/tool/approval | DAG reale, condizioni/merge/foreach/subflow, pausa/ripresa |
| P5 | Console e riuso | Builder, osservabilità, Documents chat, tool Ticket, menu flag, recovery |

Stato al 2026-10-08:

- P0: completato per inventario e provenienza; le fixture PDF sintetiche complete restano da aggiungere.
- P1: implementazione, test unitari e prenotazioni concorrenti su PostgreSQL reale completati; resta lo smoke Regolo reale.
- P2: backend/package Documents, upload privato, file completo, area PDF fail-closed e area picker Console implementati; resta la prova wheel con dipendenze e una fixture PDF multipagina reale.
- P3: modelli, ingestion, generazioni, Qdrant adapter, rivalidazione PostgreSQL e smoke Qdrant 1.15.4 reale implementati; delete/reindex end-to-end e chat con citazioni restano aperti.
- P4: DAG, condizioni, merge, JSON, tool, agente con tool loop, versioni e approvazione/ripresa implementati; foreach, sottoflow, parallelismo esplicito e restart worker restano aperti.
- P5: Console builder/lista esecuzioni, flag menu, risultato Documents e tool Ticket implementati; dettaglio trace live, recovery coordinato con Qdrant ed E2E completi restano aperti.

## 9. Test plan

Unit e API su provider, schema del grafo, budget, redazione, PDF e retrieval. Matrice anonymous/member/owner/admin/wrong-workspace e relazioni cross-workspace. Test PostgreSQL concorrenti per prenotazioni. Test Celery restart/idempotenza. Qdrant e provider fake per suite; smoke reali separati quando credenziali disponibili. Build/test Console e pacchetti prodotto. E2E Keycloak e restore con dati sentinella.

## 10. Rollout

Feature/capability disabilitata finché configurazione e infrastruttura non sono pronte. Migrare, configurare provider e budget, avviare worker, poi pubblicare flow. Attivare RAG dopo healthcheck e indice. Nessun artefatto viene dichiarato disponibile senza il relativo gate.

## 11. Removal plan

Il codice `TEMP` è solo riferimento e non entra in package o immagini. Dopo parità, mantenere una sola implementazione per provider, tracing, PDF, RAG e runner. Le implementazioni specifiche restano nei prodotti/extension o vengono rimosse quando i consumer sono migrati.

## 12. Completion criteria

P0-P5 completati con evidenze, review architetturale e di sicurezza, migration additive, artefatti coordinati e nessun accesso cross-workspace. Le verifiche non eseguibili con provider reali restano gate dichiarati.

## Diario

- 2026-10-08: ispezionati Mixtum, Fiscally, Documents, ISO e Ticket. Confermate le decisioni del piano; avviato P0.
- 2026-10-08: creato `base_modules.ai_labs` con migration additive, runtime DAG/agente, adapter provider, budget transazionale, trace redatte, versioni immutabili e approvazioni reali.
- 2026-10-08: aggiunti knowledge base/revisioni/chunk, embedding OpenAI-compatible, Qdrant e filtro autorizzativo post-retrieval.
- 2026-10-08: aggiunto il prodotto `plugins/documents`, pacchettizzato separatamente, con upload privato, ACL, parsing completo a batch, area normalizzata fail-closed, preview pagina e contributo Console.
- 2026-10-08: aggiunti tool Ticket, flag di visibilità menu separato dall'abilitazione, worker/Redis/Qdrant al template istanza e test/build locali. I gate esterni e avanzati sopra elencati non sono dichiarati completati.
- 2026-10-08: PASS su lock budget concorrente con PostgreSQL 16 e su create/upsert/search/delete dell'adapter con Qdrant 1.15.4 temporaneo; i container di prova sono stati rimossi.
