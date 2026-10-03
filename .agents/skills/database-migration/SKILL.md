---
name: database-migration
description: Progetta e revisiona migration Django/PostgreSQL Mixtum con attenzione a lock, volumi, compatibilità, backfill, rollback/recovery e deployment Kubernetes. Usare per schema change, data migration e backfill.
---

## Classifica il change
- additive;
- destructive;
- rewrite;
- index;
- constraint;
- backfill;
- rename;
- split/merge.

## Valuta produzione
Considerare:
- numero righe;
- dimensione;
- lock;
- rewrite;
- transaction;
- downtime;
- compatibilità con codice vecchio/nuovo.

## Expand / migrate / contract
Per change incompatibili preferire:
1. expand schema;
2. deploy codice compatibile;
3. backfill;
4. switch;
5. contract vecchio schema.

## Backfill
Backfill grandi:
- batch;
- idempotenti;
- osservabili;
- resumable quando utile.

Non eseguire LLM o servizi esterni in migration DB sincrone.

## Constraint/index
Valutare impatto su tabelle esistenti e strategie a basso lock.

## Rollback
Distinguere reversibilità da recovery.
Documentare entrambe quando serve.

## Kubernetes
Migration da job/processo controllato, non da tutte le replica.

## Output
Riportare:
- lock risk;
- compatibility;
- backfill;
- deployment order;
- rollback/recovery;
- test.
