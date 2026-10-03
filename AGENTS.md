# Mixtum Engineering Contract

Per modifiche complesse seguire `.agent/PLANS.md`.
Consultare `ARCHITECTURE.md`, `SECURITY.md`, `TESTING.md` e `DEFINITION_OF_DONE.md`.

## Architettura

La direzione ammessa è:

    Extension -> Plugin -> Platform -> Core

Regole:
- Core MUST NOT dipendere da plugin.
- Core MUST NOT contenere logica di un verticale.
- Platform MUST NOT dipendere da extension cliente-specifiche.
- Plugin generici MUST NOT contenere logica specifica di un cliente.
- Le extension MAY dipendere da Plugin, Platform e Core.
- Limitare plugin -> plugin.
- Preferire eventi, capability interface e service contract a import di internals.
- Qdrant, vLLM, Redis, Keycloak, S3/MinIO e provider LLM concreti sono infrastruttura/adapter.
- I verticali dipendono da capability astratte, non da implementazioni concrete.

## Prima di creare nuovo codice

Prima di creare una nuova classe, funzione condivisa, helper, service, manager, repository,
provider, client, runtime, permission system o wrapper infrastrutturale:

1. cercare nel repository implementazioni semanticamente equivalenti;
2. riusare o estendere quelle esistenti quando possibile;
3. creare una nuova abstraction solo con una necessità concreta.

Se una duplicazione è inevitabile, documentarne il motivo nel report finale.

## Minimalità

Preferire la modifica più piccola corretta.

Evitare:
- astrazioni speculative;
- wrapper inutili;
- fallback nascosti;
- feature fuori scope;
- codice morto;
- TODO vaghi;
- placeholder che sembrano implementazioni complete.

Se un refactor sostituisce davvero una vecchia implementazione:
1. migrare;
2. testare;
3. rimuovere il vecchio codice.

## Commenti

Commentare il perché, non ciò che il codice dice già.

Documentare soprattutto:
- invarianti di sicurezza;
- decisioni architetturali non ovvie;
- workaround;
- contratti pubblici;
- plugin hook;
- event contract;
- provider interface;
- AI tool con side effect.

## Sicurezza

La sicurezza è un requisito funzionale.

Per ogni operazione sensibile valutare:
- authentication;
- authorization;
- object-level authorization;
- workspace isolation;
- input validation;
- output exposure;
- auditability.

Il frontend non è un security boundary.
Un LLM non è un security boundary.
Un prompt non sostituisce authorization, validation o workspace filtering.

## Workspace

Le risorse workspace-scoped devono essere filtrate server-side.

Non fidarsi di:
- `workspace_id` client;
- foreign key client;
- ID generati da AI;
- claim non validati.

Aggiungere test cross-workspace quando applicabili.

## Keycloak

Keycloak è il centro di identity/authentication e può gestire:
- utenti;
- sessioni;
- SSO;
- MFA;
- federation;
- realm/client roles;
- gruppi.

Mixtum può mantenere:
- WorkspaceMembership;
- resource ownership;
- CourseMembership;
- TicketAssignment;
- DocumentPermission;
- ACL business fine-grained.

Non introdurre due fonti di verità modificabili indipendentemente per lo stesso concetto.

## AI Runtime

Non creare runtime AI paralleli nei verticali.

Riutilizzare le primitive condivise per:
- provider;
- model routing;
- tool execution;
- RAG;
- embeddings;
- structured output;
- tracing;
- usage/cost accounting;
- guardrail.

I plugin registrano agenti/tool/retriever, non ricreano l'orchestrazione.

## Test

Una feature non è completa con il solo happy path.

Per endpoint protetti valutare:
- anonymous;
- authenticated without permission;
- authorized;
- wrong workspace;
- object-level denial;
- cross-workspace related object;
- privilege escalation.

Non eliminare test per far passare una modifica senza spiegazione.

## Database

Le migration devono essere:
- deterministiche;
- reviewabili;
- compatibili col volume atteso;
- consapevoli di lock e rewrite;
- accompagnate da recovery/rollback se rischiose.

## Scope

Non modificare codice non correlato salvo necessità reale.

## Comandi

Non inventare comandi di build/test/lint/deploy.
Individuare quelli presenti nel repository.

## Report finale

Riportare:
- cosa è cambiato;
- file principali;
- decisioni architetturali;
- test eseguiti;
- security checks;
- verifiche non eseguite;
- migration/deployment impact;
- rischi residui.
