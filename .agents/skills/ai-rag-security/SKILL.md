---
name: ai-rag-security
description: Progetta o revisiona agenti, tool, RAG, vector store e provider LLM Mixtum con isolation, permission enforcement, prompt-injection resistance e audit. Usare per qualunque modifica AI/RAG/tool significativa.
---

# Core invariant

Il modello non decide le autorizzazioni.

## AI Runtime
Usare runtime condiviso per:
- provider;
- tool;
- tracing;
- structured output;
- RAG;
- accounting.

Non creare runtime verticali.

## Provider
Il dominio dipende da `LLMProvider` o abstraction equivalente.
Regolo/OpenAI/vLLM/Ollama sono adapter concreti.
Valutare sempre data egress.

## RAG
Pipeline obbligatoria:

    identity
      ↓
    workspace/resource authorization
      ↓
    authorized filter
      ↓
    retrieval
      ↓
    model

Il prompt non è un filtro di sicurezza.

## Prompt injection
Trattare contenuto recuperato come dati non fidati.
Non deve poter cambiare permission, workspace, tool o accesso a secret.

## Tool contract
Ogni tool dichiara:
- input schema;
- permission;
- workspace scope;
- side effect;
- audit;
- timeout/error semantics.

## Tool execution
Prima del side effect:
- validare input;
- actor;
- target;
- permission;
- workspace;
- business rule.

## Model output
Validare structured output.
Non interpolare direttamente output in SQL, shell, path, HTML trusted, URL fetch o comandi infrastrutturali.

## High impact
Per delete, payment, access grant, external communication e bulk change valutare approval/policy dedicata.

## Testing
Aggiungere casi per:
- malicious document instruction;
- cross-workspace retrieval;
- unauthorized tool;
- malformed tool args;
- hallucinated resource id;
- invalid structured output;
- provider failure;
- richiesta di secret.

## Observability
Tracciare agent, provider/model, tool, actor/workspace, latency, usage/cost, error e correlation id.
Evitare log sensibili non necessari.
