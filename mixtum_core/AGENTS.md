# Backend / Django Rules

Queste regole specializzano il `AGENTS.md` root per Django/DRF/Celery.

## Boundary
- Evitare import di modelli interni tra plugin salvo contratto esplicito.
- Business logic riusabile non deve vivere solo in view/serializer.
- Evitare signal per flow critici se nascondono side effect; preferire service/event espliciti.
- Queryset/manager devono rispettare workspace scope.

## DRF
Per ogni endpoint valutare:
1. authentication;
2. permission;
3. scoped queryset;
4. object permission;
5. validation;
6. side effect;
7. audit.

Non derivare ownership/workspace da input client senza validazione.

## ORM
- Preferire ORM parametrizzato.
- Evitare N+1.
- Usare `select_related`/`prefetch_related` dove serve.
- Valutare transaction/locking per update concorrenti.

## Transactions
Operazioni multi-step atomiche devono usare transaction.
Evitare side effect esterni dentro transaction lunghe quando possibile.

## Celery
Task:
- idempotenti quando possibile;
- retry-safe;
- osservabili;
- workspace-aware;
- con timeout/retry espliciti quando opportuno.

## Test
Per API workspace-scoped usare almeno due workspace nei test negativi.
