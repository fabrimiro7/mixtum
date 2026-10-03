---
name: kubernetes-deployment
description: Progetta o modifica deployment Docker/Kubernetes Mixtum con servizi opzionali, health check, security context, secret, migration e dependency resolution. Usare per compose, Helm, manifest, container e runtime infrastructure.
---

## Capability-driven infrastructure
Derivare servizi dalle capability:

    provider=regolo -> vLLM not required
    rag=false -> Qdrant not required
    vector_store=qdrant -> Qdrant required

## Container
Verificare:
- pinned base image;
- multi-stage se utile;
- non-root;
- no secret baked;
- healthcheck;
- graceful shutdown.

## Kubernetes
Verificare:
- workload appropriato;
- startup/readiness/liveness;
- resource policy;
- ServiceAccount;
- RBAC;
- Secret;
- network exposure.

## Network
Servizi interni ClusterIP/non pubblici salvo requisito.
Valutare NetworkPolicy.

## Migration
Usare migration job controllato.

## Stateful
Per Postgres/Qdrant/storage:
- PVC;
- backup;
- restore;
- upgrade;
- capacity;
- failure mode.

## Security
Valutare:
- runAsNonRoot;
- Linux capabilities;
- readOnlyRootFilesystem quando compatibile;
- privileged mode;
- image scanning.

## Validation
Usare strumenti realmente presenti nel repo per compose/Helm/manifests/security.
