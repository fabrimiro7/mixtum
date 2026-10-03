---
name: security-review
description: Esegue una revisione di sicurezza avversariale di una modifica Mixtum, con focus su authorization, workspace isolation, input, file, API, AI/RAG, Keycloak e infrastruttura. Usare per feature sensibili, review pre-merge e release.
---

Assumere che possano esserci vulnerabilità.
Cercare modi realistici per rompere gli invarianti.

## Scope
Identificare entry point, actor, trust boundary, dati sensibili, side effect e workspace.

## Authentication
Verificare accesso anonymous, token validation e service account.

## Authorization
Provare:
- user senza ruolo;
- object ID di altra risorsa;
- workspace differente;
- foreign key cross-workspace;
- modifica di owner/role/workspace via input;
- bulk endpoint;
- IDOR.

## Input/output
Controllare validation, path, URL, file, SQL, template, serializzazione, dati sensibili e log.

## AI/RAG
Controllare:
- prompt injection;
- indirect prompt injection;
- tool permission;
- tool args;
- workspace retrieval;
- ACL;
- output validation;
- provider data egress;
- side effect;
- audit.

Regola:

    authorization -> retrieval -> model

mai retrieval globale seguito da filtro affidato al prompt.

## File
Valutare MIME spoof, traversal, ACL, public URL, overwrite, executable upload, size bomb.

## External request
Valutare SSRF e redirect.

## Infrastructure
Valutare secret, public exposure, container user, RBAC, ServiceAccount e default unsafe.

## Output
Classificare finding:
- Critical;
- High;
- Medium;
- Low;
- Informational.

Per ogni finding:
- titolo;
- path/componente;
- scenario;
- impatto;
- evidenza;
- fix;
- regression test.

Separare finding confermati, rischi potenziali e verifiche non eseguibili.
