# Packaging backend Mixtum 0.1.0 (prova tecnica)

`pyproject.toml` costruisce `mixtum-platform-backend==0.1.0` da `mixtum_core` e `base_modules`. Ticket, Links, plugin example ed extension restano distribuzioni distinte; il wheel Platform non li contiene. Le migration delle app condivise mantengono app label e nomi, senza riscrivere lo schema. Le dipendenze dichiarate derivano da `requirements.txt`; per riprodurre l'ambiente usare anche `requirements-baseline.lock` (copiato come `constraints.txt` nel template d'istanza).

Da un checkout Mixtum:

```bash
python -m pip wheel --no-deps --wheel-dir /percorso/wheelhouse .
python -m pip wheel --no-deps --wheel-dir /percorso/wheelhouse ./plugins/ticket
python scripts/verify-platform-wheel.py /percorso/wheelhouse/mixtum_platform_backend-0.1.0-py3-none-any.whl
bash scripts/create-project.sh /percorso/istanza
cd /percorso/istanza
make install-wheels WHEELHOUSE=/percorso/wheelhouse PYTHON=/percorso/python3.12
make wheel-check
.venv/bin/python -m pip check
```

La prova locale ha installato Platform e Ticket in un virtualenv nuovo e applicato le migration su un SQLite dedicato nella directory dell'istanza; `django check` passa anche in modalità Keycloak. Lo sdist della piattaforma è stato ricostruito in wheel e ha superato lo stesso controllo dei contenuti. Non è stata toccata alcuna istanza esistente. La CI ripete build, ispezione e installazione pulita, ma il runner non è ancora stato osservato.

Il Dockerfile attuale dell'istanza installa i wheel da `vendor/wheels`; la Console può essere costruita dal bundle versionato senza checkout Mixtum. Limiti ancora aperti: i pacchetti non sono pubblicati, il lock Python deriva dalla baseline Linux ed è da rivalidare sui target, e il ciclo completo dell'istanza deve essere verificato con PostgreSQL/Keycloak reali. Prima della release servono inoltre backup/ripristino e aggiornamento provati. Disabilitare un plugin non deve invertire automaticamente le sue migration né cancellarne i dati. Vedere lo [stato consolidato](../plans/2026-10-03-stato-e-roadmap-handoff.md) per l'ordine delle verifiche.
