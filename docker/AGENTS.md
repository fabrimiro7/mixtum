# Mixtum Infrastructure Rules

## Capability-driven deployment
L'infrastruttura deriva dalla configurazione.

Esempi:
- provider Regolo -> vLLM non richiesto;
- RAG off -> Qdrant non richiesto salvo altro uso;
- backend pgvector -> Qdrant non richiesto.

## Container
- immagini versionate;
- evitare `latest` in produzione;
- no secret nell'immagine;
- non-root dove possibile;
- healthcheck;
- graceful shutdown.

## Kubernetes
- probe appropriate;
- resource request/limit secondo strategia;
- ServiceAccount minimo;
- RBAC least privilege;
- Secret separati da config;
- evitare esposizione pubblica di servizi interni.

## Migration
Non eseguire migration concorrenti da ogni replica.
Usare job/processo controllato.

## Stateful
Per Postgres/Qdrant/storage considerare persistenza, backup, restore, upgrade e capacity.
