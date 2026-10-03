---
name: implement-feature
description: Implementa una feature Mixtum end-to-end rispettando architettura, riuso, test, sicurezza e Definition of Done. Usare per nuove funzionalità o modifiche funzionali non banali.
---

# Workflow

1. Leggere il `AGENTS.md` applicabile.
2. Leggere `ARCHITECTURE.md`, `SECURITY.md`, `TESTING.md`, `DEFINITION_OF_DONE.md`.
3. Se richiesto da `.agent/PLANS.md`, creare/aggiornare un ExecPlan.
4. Cercare implementazioni semanticamente equivalenti.
5. Identificare layer, workspace scope, permission e capability.
6. Definire la modifica minima.
7. Implementare.
8. Scrivere/aggiornare test.
9. Fare security check proporzionato.
10. Fare architecture review del diff.
11. Eseguire test/lint/typecheck/build/security tool disponibili.
12. Rimuovere codice obsoleto reso inutile.
13. Aggiornare doc/ADR.
14. Produrre report finale.

# Anti-slop

Prima di chiudere:
- Ho duplicato un helper/service/provider?
- Ho creato un'astrazione senza necessità?
- Ho aggiunto fallback che nasconde errori?
- Ho duplicato authorization logic?
- Ho messo logica cliente in un plugin generico?
- Ho usato direttamente Qdrant/vLLM/provider in un verticale?
- Ho lasciato vecchia e nuova implementazione senza removal plan?
- Ho aggiunto commenti ovvi?

Se sì, correggere o documentare il motivo.
