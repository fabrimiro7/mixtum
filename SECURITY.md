# Mixtum Security Engineering Policy

## Trust boundaries

Considerare non fidati:
- browser;
- frontend;
- input API;
- header/query string;
- upload;
- webhook;
- documenti e contenuti RAG;
- output LLM;
- tool arguments generati dal modello;
- dati di provider esterni.

Il backend impone le regole.

## Authentication

Con Keycloak validare correttamente:
- firma;
- issuer;
- audience/client;
- expiration;
- token type dove rilevante.

L'identità deriva dal token validato, non da campi client.

## Authorization

Distinguere:
- global/client role;
- workspace membership;
- resource permission;
- business rule.

Un ruolo globale non implica automaticamente accesso a ogni oggetto.

## Workspace isolation

Per query workspace-scoped:
- derivare lo scope dal contesto autorizzato;
- limitare la queryset;
- validare oggetti correlati;
- impedire riferimenti cross-workspace.

Conoscere l'ID di una risorsa non deve permettere IDOR.

## Frontend

Route guard, menu e hide/show sono UX.
L'enforcement reale è backend.

## Input

Validare:
- tipo;
- formato;
- range;
- enum;
- relazioni;
- ownership;
- workspace;
- dimensione;
- MIME/file;
- URL/path.

## File handling

Per upload/documentale:
- limitare size;
- verificare tipo reale quando necessario;
- generare storage name safe;
- impedire path traversal;
- evitare esecuzione;
- applicare ACL;
- evitare URL pubbliche permanenti per documenti privati;
- considerare malware scanning nei flussi ad alto rischio.

## SSRF

Per URL influenzati dall'utente valutare:
- loopback;
- link-local;
- metadata service;
- reti private;
- schemi vietati;
- redirect verso target vietati.

## Secrets

Non:
- committare secret;
- loggare token;
- loggare Authorization header;
- esporre API key al frontend;
- inserire credenziali nei manifest versionati.

## Logging e audit

Per azioni sensibili registrare dove opportuno:
- actor;
- workspace;
- action;
- target;
- timestamp;
- esito;
- correlation id.

## Webhook

Valutare:
- firma/autenticità;
- replay;
- idempotenza;
- timestamp;
- deduplicazione.

## AI

L'output del modello è input non fidato.

Non usarlo direttamente per:
- SQL raw;
- shell;
- path;
- URL fetch;
- autorizzazione;
- comandi infrastrutturali;
- operazioni distruttive;
senza validation/policy.

## Prompt injection

Assumere che documenti, ticket, email e contenuti RAG possano contenere prompt injection.

Il contenuto recuperato non può:
- ampliare permessi;
- cambiare workspace;
- ottenere tool extra;
- leggere secret;
- bypassare policy.

## RAG authorization invariant

> Authorization happens before retrieval results are exposed to the model.

Pipeline corretta:

    authenticated user
      ↓
    authorized workspace/resource scope
      ↓
    vector/database filter
      ↓
    retrieval
      ↓
    LLM

Mai fare retrieval globale e affidarsi al prompt per ignorare contenuti non autorizzati.

## Vector store

Ogni vettore workspace-scoped deve avere metadata sufficienti per applicare il filtro autorizzativo.

Testare:
- isolamento workspace;
- ACL;
- delete;
- reindex;
- revoca accesso.

## AI tools

Ogni tool dichiara almeno:
- name;
- purpose;
- input schema;
- permission;
- workspace scope;
- side-effect level;
- audit policy.

Prima di un side effect validare di nuovo:
- actor;
- permission;
- target;
- workspace;
- input.

## Keycloak

Valutare:
- redirect URI esatte;
- Web Origins restrittive;
- client type;
- PKCE per public client;
- token lifetime;
- service account privilege;
- role/group mapping.

## Database

Preferire ORM parametrizzato.
SQL raw richiede motivazione, parametrizzazione e test.

## Containers/K8S

Applicare least privilege a:
- container user;
- ServiceAccount;
- RBAC;
- Secrets;
- network exposure.

Non esporre Postgres, Redis, Qdrant o vLLM pubblicamente senza requisito.

## Review output

Classificare finding:
- Critical;
- High;
- Medium;
- Low;
- Informational.

Per ogni finding indicare:
- componente;
- scenario;
- impatto;
- evidenza;
- fix;
- regression test.
