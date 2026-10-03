---
name: release-review
description: Esegue il gate finale di una milestone o release Mixtum verificando test, security, migration, dependency, deployment, documentazione e rimozione legacy. Usare prima di release significative.
---

## Code
- nessuna duplicazione critica nota;
- niente temporary implementation lasciata senza piano;
- boundary rispettati;
- nuove dependency giustificate.

## Tests
- suite rilevanti verdi;
- security regression verdi;
- cross-workspace verdi;
- frontend build verde;
- migration test eseguiti quando necessari.

## Security
Eseguire `security-review` sulle aree modificate.
Controllare vulnerability scan disponibile.

## Database
Verificare migration order, lock risk, backfill, recovery e compatibility.

## Infrastructure
Verificare config, secret, optional service, probe, resource impact e deployment order.

## Compatibility
Verificare API, plugin compatibility, SDK, Keycloak config ed event contract.

## Documentation
Verificare architecture, security, config, release note e ADR.

## Output
Produrre checklist:
- PASS;
- FAIL;
- NOT RUN;
- NOT APPLICABLE.

Una voce FAIL impedisce di dichiarare la release pronta.
Una voce NOT RUN richiede motivazione.
