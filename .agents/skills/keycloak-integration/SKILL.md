---
name: keycloak-integration
description: Progetta o modifica integrazione Keycloak Mixtum per Django e frontend, distinguendo identità, ruoli globali e autorizzazioni di dominio. Usare per OIDC, SSO, role mapping, workspace membership e service account.
---

## Ownership
Keycloak authoritative per:
- identity;
- authentication;
- session;
- MFA;
- federation;
- realm/client role;
- gruppi quando previsto dal design.

Mixtum può essere authoritative per:
- WorkspaceMembership;
- resource ownership;
- relazioni dominio;
- ACL fine-grained.

Non creare identità parallele senza necessità.

## Backend
Validare:
- signature;
- issuer;
- audience;
- expiration;
- claim richiesti.

Usare `sub` come identifier stabile quando appropriato.

## Frontend
Per public client:
- Authorization Code + PKCE secondo configurazione;
- niente client secret;
- redirect URI minimali;
- Web Origins restrittive.

## Roles
Usare Keycloak per ruoli relativamente stabili.
Evitare role explosion per singola risorsa se la relazione appartiene al dominio.

## Workspace
Se i gruppi Keycloak rappresentano workspace, definire chiaramente source of truth e sync.

## Service account
Least privilege.

## Test
Testare:
- valid token;
- expired/invalid;
- wrong issuer/audience;
- missing role;
- correct role;
- domain/workspace authorization indipendente dal ruolo globale.
