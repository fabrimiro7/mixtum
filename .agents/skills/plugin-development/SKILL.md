---
name: plugin-development
description: Crea o modifica un plugin Mixtum installabile, definendone manifest, capability, permissions, events, workspace behavior e frontend registration senza coupling improprio. Usare per Ticket, Documents, Academy, Events o nuovi verticali.
---

## Prima domanda
Verificare che sia davvero Plugin e non Core, Platform capability o customer Extension.

## Manifest
Definire:
- name/version;
- core compatibility;
- required/optional capability;
- permissions;
- backend entrypoint;
- console registration;
- emitted/consumed events.

## Backend
- ownership DB chiara;
- workspace scope;
- migration indipendenti;
- public service contract esplicito.

## Frontend
Registrare route/navigation/settings/widget tramite extension mechanism previsto.

## Inter-plugin
Preferire:
1. event;
2. shared capability;
3. stable service interface.

## AI
Registrare agent/tool/retriever nel runtime condiviso.

## Infrastructure
Dichiarare requirement, non avviare direttamente container.

## Test
Coprire:
- enabled;
- permission;
- workspace isolation;
- event contract;
- disabled behavior;
- optional capability behavior.
