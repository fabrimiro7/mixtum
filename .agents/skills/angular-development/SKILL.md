---
name: angular-development
description: Implementa o modifica Mixtum Console/Public Frontend Angular rispettando plugin composition, Keycloak/OIDC, branding, API contracts, UX permissions e test. Usare per componenti, route, service, guard e frontend plugin.
---

## Principi
- Console core comune.
- No logica cliente-specifica nel core.
- UI permission non equivale a security.
- Keycloak/OIDC condiviso.
- Branding token condivisi.
- SDK/tipi OpenAPI quando disponibili.

## Workflow
1. Identificare Console core, plugin UI, Public Frontend o Extension.
2. Cercare component/service/guard equivalenti.
3. Definire state ownership.
4. Implementare.
5. Gestire loading/error/empty/forbidden.
6. Aggiungere test.
7. Verificare accessibility base.
8. Eseguire lint/test/build disponibili.

## Anti-pattern
Non:
- duplicare API model;
- hardcodare branding cliente;
- memorizzare client secret;
- fidarsi della sola route guard;
- creare un secondo auth service.
