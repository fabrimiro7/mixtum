# Mixtum Testing Strategy

## Principio

I test devono dimostrare comportamento e invarianti, non soltanto aumentare coverage.

## Livelli

Usare in modo proporzionato:
- unit;
- domain/service;
- API integration;
- permission;
- migration;
- frontend component;
- e2e;
- security regression.

## Backend API matrix

Per endpoint protetti valutare:

| Scenario | Aspettativa |
|---|---|
| anonymous | reject |
| authenticated without permission | reject |
| authorized | success |
| resource in another workspace | reject/not found secondo policy |
| related object from another workspace | reject |
| malformed input | reject |
| privilege escalation input | reject |

## Workspace

Quando si verifica isolamento, usare almeno due workspace nei test.

## Regression

Ogni bug di sicurezza/autorizzazione corretto dovrebbe produrre un test che riproduce il bug.

## AI

Testare separatamente:
- provider adapter;
- tool schema;
- permission enforcement;
- structured output;
- RAG filters;
- provider failure;
- orchestration model-independent.

Per la business logic preferire fake/stub provider a output LLM non deterministico.

## RAG

Minimo:
- indicizzazione;
- search;
- workspace filter;
- ACL filter;
- delete;
- reindex;
- empty result;
- prompt injection content.

## Keycloak

Separare:
- authorization locale;
- integration OIDC;
- e2e login dove disponibile.

## Migration

Per migration rischiose testare:
- upgrade da stato precedente;
- dati realistici;
- constraint;
- default/null;
- recovery quando possibile.

## Frontend

Testare soprattutto:
- routing;
- permission-dependent UI;
- error/loading/empty;
- workspace switch;
- flussi critici.

I test frontend non sostituiscono quelli backend.

## Chiusura

Eseguire i comandi reali disponibili per:
- test;
- lint;
- type check;
- build;
- security scanning.

Riportare ciò che non è stato possibile eseguire.

Per riprodurre le suite Python locali senza PostgreSQL:

```bash
python3.12 -m unittest discover -s tests -p 'test_*.py' -q
SECRET_KEY=test-only-secret POSTGRES_HOST= USE_S3=0 AUTH_MODE=django MIXTUM_SQLITE_TEST_DB=:memory: DJANGO_SETTINGS_MODULE=tests.fixtures.sqlite_settings python3.12 manage.py test --noinput
```

La suite Django include un test JWKS che apre un server HTTP su `127.0.0.1`; eseguirla in un ambiente che consenta il loopback. Queste suite non sostituiscono le prove reali con PostgreSQL e Keycloak.
