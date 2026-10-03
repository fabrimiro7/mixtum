# Mixtum Definition of Done

## Implementazione

- [ ] Comportamento richiesto implementato.
- [ ] Nessuna feature fuori scope.
- [ ] Nessuna primitive equivalente ignorata.
- [ ] Nessuna duplicazione non motivata.
- [ ] Vecchio codice rimosso quando realmente sostituito.
- [ ] Boundary Core / Platform / Plugin / Extension rispettate.
- [ ] Verticali non dipendono direttamente da provider infrastrutturali.

## Sicurezza

- [ ] Authentication valutata.
- [ ] Authorization valutata.
- [ ] Object authorization valutata.
- [ ] Workspace isolation valutata.
- [ ] Input/output exposure valutati.
- [ ] Audit/logging valutati.
- [ ] AI/RAG/tool security valutata se applicabile.
- [ ] Security regression test aggiunti se applicabili.

## Test

- [ ] Test pertinenti eseguiti.
- [ ] Nuovi test aggiunti.
- [ ] Happy path coperto.
- [ ] Failure path importante coperto.
- [ ] Negative permission test quando applicabili.
- [ ] Cross-workspace test quando applicabili.

## Qualità

- [ ] Lint eseguito dove disponibile.
- [ ] Type check eseguito dove disponibile.
- [ ] Build eseguita dove applicabile.
- [ ] Nessun warning rilevante ignorato.
- [ ] Commenti solo dove utili.
- [ ] Public contract documentati.

## Database / deploy

- [ ] Migration reviewata se presente.
- [ ] Lock/volume impact valutato.
- [ ] Recovery/rollback definito per change rischiosi.
- [ ] Docker/K8S impact valutato.
- [ ] Secret/config impact valutato.
- [ ] Servizi opzionali attivati solo se richiesti.

## Documentazione

- [ ] Architecture aggiornata se cambia un boundary.
- [ ] Security aggiornata se cambia una policy.
- [ ] Config/manifest documentati.
- [ ] ADR aggiunto per decisioni rilevanti.

## Report finale

Indicare:
1. modifiche;
2. test;
3. security review;
4. verifiche non eseguite;
5. migration/deployment impact;
6. rischi residui.
