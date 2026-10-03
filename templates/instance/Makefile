.PHONY: check check-config install-wheels wheel-check stage-wheels plugin-register plugin-backend-editable backend-dev console-build console-add-package console-dev prepare up stop logs snapshot-volumes restore-volumes

PYTHON ?= python3.12
BACKEND_DEV_PORT ?= 8000

check-config:
	@test -f .env || { echo '.env non trovato.' >&2; exit 1; }
	@set -a; . ./.env; set +a; \
	 test -n "$$SECRET_KEY" && test "$$SECRET_KEY" != changeme && \
	 test -n "$$POSTGRES_PASSWORD" && test -n "$$KEYCLOAK_ADMIN_PASSWORD" || \
	 { echo 'Configurazione incompleta: imposta SECRET_KEY, POSTGRES_PASSWORD e KEYCLOAK_ADMIN_PASSWORD senza valori predefiniti.' >&2; exit 1; }

check:
	@test -x .venv/bin/python || { echo 'Prima esegui make install-wheels WHEELHOUSE=...' >&2; exit 1; }
	@set -a; . ./.env; set +a; \
	 POSTGRES_HOST= .venv/bin/python manage.py check

install-wheels:
	@test -n "$(WHEELHOUSE)" || { echo 'Specifica WHEELHOUSE=/percorso/wheelhouse.' >&2; exit 1; }
	$(PYTHON) -m venv .venv
	.venv/bin/python -m pip install --find-links "$(WHEELHOUSE)" -c constraints.txt -r requirements.txt

wheel-check:
	@test -x .venv/bin/python || { echo 'Prima esegui make install-wheels WHEELHOUSE=...' >&2; exit 1; }
	@.venv/bin/python -m pip check
	@set -a; . ./.env; set +a; \
	 POSTGRES_HOST= .venv/bin/python manage.py check

stage-wheels:
	@test -n "$(WHEELHOUSE)" || { echo 'Specifica WHEELHOUSE=/percorso/wheelhouse.' >&2; exit 1; }
	@mkdir -p vendor/wheels
	$(PYTHON) -m pip download --no-index --no-deps --find-links "$(WHEELHOUSE)" -d vendor/wheels -r requirements.txt

plugin-register:
	@test -n "$(PLUGIN_SOURCE)" || { echo 'Specifica PLUGIN_SOURCE=/percorso/plugin.' >&2; exit 1; }
	$(PYTHON) tools/register-plugin.py "$(PLUGIN_SOURCE)"

plugin-backend-editable:
	@test -x .venv/bin/python || { echo 'Prima esegui make install-wheels WHEELHOUSE=...' >&2; exit 1; }
	@test -n "$(PLUGIN_SOURCE)" && test -f "$(PLUGIN_SOURCE)/backend/pyproject.toml" || { echo 'Specifica PLUGIN_SOURCE=/percorso/plugin con backend/pyproject.toml.' >&2; exit 1; }
	.venv/bin/python -m pip install --no-deps -e "$(PLUGIN_SOURCE)/backend"
	.venv/bin/python -m pip check

backend-dev:
	@test -x .venv/bin/python || { echo 'Prima esegui make install-wheels WHEELHOUSE=...' >&2; exit 1; }
	@set -a; . ./.env; set +a; \
	 .venv/bin/python manage.py runserver "127.0.0.1:$(BACKEND_DEV_PORT)"

console-build:
	@set -a; . ./.env; set +a; \
	 CONSOLE_BUNDLE="$(CONSOLE_BUNDLE)" bash ./tools/build-console.sh "$(CURDIR)"

console-add-package:
	@test -n "$(PACKAGE)" || { echo 'Specifica PACKAGE=/percorso/plugin.tgz.' >&2; exit 1; }
	@set -a; . ./.env; set +a; \
	 CONSOLE_BUNDLE="$(CONSOLE_BUNDLE)" bash ./tools/build-console.sh --add-package "$(CURDIR)" "$(PACKAGE)"

console-dev:
	@test -n "$(PLUGIN_SOURCE)" || { echo 'Specifica PLUGIN_SOURCE=/percorso/plugin/console.' >&2; exit 1; }
	@set -a; . ./.env; set +a; \
	 CONSOLE_BUNDLE="$(CONSOLE_BUNDLE)" CONSOLE_DEV_PORT="$(CONSOLE_DEV_PORT)" \
	 bash ./tools/build-console.sh --dev "$(CURDIR)" "$(PLUGIN_SOURCE)"

prepare: check-config
	@test -d vendor/wheels || { echo 'Prima esegui make stage-wheels WHEELHOUSE=...' >&2; exit 1; }
	docker compose --env-file .env build web
	docker compose --env-file .env up -d db keycloak
	docker compose --env-file .env run --rm web python manage.py migrate --noinput

up:
	@test -f artifacts/console/browser/index.html || { echo 'Prima esegui make console-build.' >&2; exit 1; }
	docker compose --env-file .env up -d web console

stop:
	docker compose --env-file .env down

snapshot-volumes:
	@test -n "$(SNAPSHOT_DIR)" || { echo 'Specifica SNAPSHOT_DIR=/percorso/nuovo-snapshot.' >&2; exit 1; }
	bash ./tools/snapshot-volumes.sh "$(SNAPSHOT_DIR)"

restore-volumes:
	@test -n "$(SNAPSHOT_DIR)" || { echo 'Specifica SNAPSHOT_DIR=/percorso/snapshot-completo.' >&2; exit 1; }
	bash ./tools/restore-volumes.sh "$(SNAPSHOT_DIR)"

logs:
	docker compose --env-file .env logs -f web console keycloak
