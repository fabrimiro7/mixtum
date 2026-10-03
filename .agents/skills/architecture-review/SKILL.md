---
name: architecture-review
description: Verifica che una modifica Mixtum rispetti Core, Platform, Plugin, Extension, dependency direction, capability abstraction e modular monolith. Usare per refactor, nuovi moduli, plugin, servizi e PR significative.
---

# Invariant

    Extension -> Plugin -> Platform -> Core

## Placement
Per ogni nuovo modulo chiedere:
- è Core?
- capability condivisa?
- verticale?
- cliente-specifico?

## Dependency
Cercare:
- Core -> Plugin;
- Platform -> Extension;
- Plugin generico -> customer code;
- internals di un plugin importati da altro plugin;
- vertical -> Qdrant/vLLM/Regolo diretto;
- vertical -> nuovo AI runtime.

## Duplication
Cercare duplicati semantici:
- agent runner;
- provider;
- vector store;
- permission service;
- workspace helper;
- event dispatcher;
- payment client;
- notification abstraction.

## Coupling
Valutare eventi/capability/service contract al posto di import diretti.

## Microservices
Se è stato estratto un servizio, verificare ragione operativa concreta:
scaling, trust boundary, lifecycle, load o condivisione multi-istanza.

## Legacy
Controllare se convivono vecchia e nuova implementazione senza removal plan.

## Output
Riportare:
- invarianti rispettati;
- violazioni;
- coupling;
- duplicazioni;
- raccomandazioni;
- eventuale ADR necessaria.
