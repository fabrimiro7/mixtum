# Mixtum ExecPlans

Un ExecPlan è obbligatorio quando una modifica:
- cambia boundary architetturali;
- modifica authentication/authorization;
- modifica workspace isolation;
- introduce/ristruttura plugin;
- modifica AI Runtime o RAG;
- introduce capability infrastrutturale;
- modifica schema DB significativamente;
- coinvolge più sottosistemi;
- modifica Docker/Kubernetes;
- richiede migrazione legacy.

## Struttura obbligatoria

### 1. Goal
Risultato osservabile.

### 2. Non-goals
Cosa non cambia.

### 3. Current state
Moduli, flow, problemi e path reali.

### 4. Target architecture
Responsibility, dependencies, interface, event contract, schema/config.

Verificare:

    Extension -> Plugin -> Platform -> Core

### 5. Security impact
Valutare auth, authorization, workspace, secret, AI/RAG, file, external call, privilege escalation.

### 6. Data/migration impact
Schema, backfill, lock, compatibility, recovery.

### 7. Deployment impact
Env, Docker, K8S, Keycloak, Qdrant, vLLM, secret, servizi opzionali.

### 8. Milestones
Per ogni milestone:
- modifica;
- file;
- acceptance criteria;
- test;
- validation commands.

Se la validazione fallisce, correggere prima di proseguire.

### 9. Test plan
Unit, integration, permission, workspace, security regression, migration, frontend/e2e.

### 10. Rollout
Ordine, compatibility, feature flag se utile, rollback, monitoring.

### 11. Removal plan
Indicare quando viene eliminato il codice sostituito.

### 12. Completion criteria
Applicare `DEFINITION_OF_DONE.md`.

## Living document

Aggiornare il piano quando cambiano assunzioni o design.

Posizione suggerita:

    docs/plans/YYYY-MM-DD-nome-task.md
