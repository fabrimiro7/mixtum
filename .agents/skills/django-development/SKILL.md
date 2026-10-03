---
name: django-development
description: Implementa o modifica backend Django/DRF/Celery Mixtum seguendo workspace isolation, authorization, transaction safety, query efficiency e test. Usare per model, API, serializer, service, task e permission backend.
---

1. Identificare app/layer proprietario.
2. Verificare workspace scope.
3. Cercare service/permission/queryset esistenti.
4. Definire contract.
5. Implementare business logic nel layer riusabile appropriato.
6. Applicare permission e queryset scope.
7. Gestire transaction/locking.
8. Scrivere test funzionali e negativi.
9. Controllare N+1 nei path critici.
10. Eseguire verifiche disponibili.

## DRF checklist
- authentication;
- permission;
- scoped queryset;
- object permission;
- serializer validation;
- related object ownership;
- workspace consistency;
- audit.

## Serializer
Business invariant riusate da più entry point non devono vivere solo nel serializer.

## Celery
Task idempotente/retry-safe quando possibile.
Ricostruire e validare scope server-side.

## SQL
Preferire ORM.
SQL raw richiede motivo, parametri e test.
