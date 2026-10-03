# Mixtum + Codex Engineering Pack

Questo pacchetto definisce come Codex deve lavorare sul repository Mixtum.

## Obiettivo

Ridurre:
- duplicazione;
- slop;
- fork cliente-specifici;
- coupling tra plugin;
- vulnerabilità di autorizzazione;
- regressioni cross-workspace;
- runtime AI duplicati;
- infrastruttura avviata senza necessità.

## Gerarchia

1. `AGENTS.md`: invarianti repository-wide.
2. `ARCHITECTURE.md`, `SECURITY.md`, `TESTING.md`, `DEFINITION_OF_DONE.md`: policy dettagliate.
3. `.agent/PLANS.md`: regole per gli ExecPlan.
4. `.agents/skills/*/SKILL.md`: workflow specialistici.
5. `AGENTS.md` locali: specializzano backend, frontend, plugin e infrastruttura.

## Regola fondamentale

    Extension -> Plugin -> Platform -> Core

Il Core non conosce i plugin.
La Platform non conosce le customizzazioni cliente.
I plugin generici non contengono logica cliente-specifica.
Le extension possono dipendere dai layer inferiori, mai il contrario.

## Prima di iniziare la grande rifattorizzazione

1. Copiare questi file nel repository.
2. Adattare i path alle directory reali.
3. Inserire i comandi reali di test/lint/build.
4. Collegare alla CI i controlli automatici.
5. Far eseguire una `architecture-review` del repository attuale.
6. Creare un ExecPlan per la migrazione.
7. Procedere per milestone verificabili.
