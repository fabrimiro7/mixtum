.PHONY: setup dev dev-d prod prod-prepare stop migrate shell logs restart rebuild hard-rebuild

# Il nome del progetto è salvato in .env dal setup; se assente, usa la cartella.
# Le variabili d'ambiente della shell non sovrascrivono l'istanza configurata.
COMPOSE_PROJECT_NAME := $(shell sed -n 's/^COMPOSE_PROJECT_NAME=//p' '$(CURDIR)/.env' 2>/dev/null | sed -n '1p' | tr '[:upper:]' '[:lower:]' | sed 's/[^a-z0-9_-]/-/g' | sed 's/--*/-/g' | sed 's/^-*//;s/-*$$//')
# Fallback: se .env non esiste o non ha COMPOSE_PROJECT_NAME, usa il nome della cartella normalizzato
ifeq ($(strip $(COMPOSE_PROJECT_NAME)),)
COMPOSE_PROJECT_NAME := $(shell basename '$(CURDIR)' | tr '[:upper:]' '[:lower:]' | tr -cs 'a-z0-9' '-' | sed 's/^-*//;s/-*$$//')
endif

# Percorsi assoluti quotati: ok anche se la cartella progetto ha spazi nel path
ENV_FILE := $(CURDIR)/.env
F_COMPOSE_BASE := $(CURDIR)/docker/docker-compose.yml
F_COMPOSE_LOCAL := $(CURDIR)/docker/docker-compose.local.yml
F_COMPOSE_OVERRIDE := $(CURDIR)/docker/docker-compose.override.yml
F_COMPOSE_PROD := $(CURDIR)/docker/docker-compose.prod.yml

# ─────────────────────────────────────────
# SETUP
# ─────────────────────────────────────────

setup:
	bash scripts/setup.sh

# ─────────────────────────────────────────
# SVILUPPO LOCALE
# ─────────────────────────────────────────

dev:
	docker compose -p "$(COMPOSE_PROJECT_NAME)" --env-file "$(ENV_FILE)" -f "$(F_COMPOSE_BASE)" \
	               -f "$(F_COMPOSE_LOCAL)" \
	               -f "$(F_COMPOSE_OVERRIDE)" up

dev-d:
	docker compose -p "$(COMPOSE_PROJECT_NAME)" --env-file "$(ENV_FILE)" -f "$(F_COMPOSE_BASE)" \
	               -f "$(F_COMPOSE_LOCAL)" \
	               -f "$(F_COMPOSE_OVERRIDE)" up -d

# ─────────────────────────────────────────
# PRODUZIONE
# ─────────────────────────────────────────

prod-prepare:
	docker compose -p "$(COMPOSE_PROJECT_NAME)" --env-file "$(ENV_FILE)" -f "$(F_COMPOSE_BASE)" \
	               -f "$(F_COMPOSE_PROD)" build web
	docker compose -p "$(COMPOSE_PROJECT_NAME)" --env-file "$(ENV_FILE)" -f "$(F_COMPOSE_BASE)" \
	               -f "$(F_COMPOSE_PROD)" up -d db
	docker compose -p "$(COMPOSE_PROJECT_NAME)" --env-file "$(ENV_FILE)" -f "$(F_COMPOSE_BASE)" \
	               -f "$(F_COMPOSE_PROD)" run --rm --no-deps web migrate

prod: prod-prepare
	docker compose -p "$(COMPOSE_PROJECT_NAME)" --env-file "$(ENV_FILE)" -f "$(F_COMPOSE_BASE)" \
	               -f "$(F_COMPOSE_PROD)" up -d --no-build

# ─────────────────────────────────────────
# GESTIONE
# ─────────────────────────────────────────

stop:
	docker compose -p "$(COMPOSE_PROJECT_NAME)" --env-file "$(ENV_FILE)" -f "$(F_COMPOSE_BASE)" \
	              -f "$(F_COMPOSE_LOCAL)" \
	              -f "$(F_COMPOSE_OVERRIDE)" down

migrate:
	docker compose -p "$(COMPOSE_PROJECT_NAME)" --env-file "$(ENV_FILE)" -f "$(F_COMPOSE_BASE)" \
	              -f "$(F_COMPOSE_LOCAL)" \
	              -f "$(F_COMPOSE_OVERRIDE)" run --rm --no-deps web migrate

makemigrations:
	docker compose -p "$(COMPOSE_PROJECT_NAME)" --env-file "$(ENV_FILE)" -f "$(F_COMPOSE_BASE)" \
	              -f "$(F_COMPOSE_LOCAL)" \
	              -f "$(F_COMPOSE_OVERRIDE)" exec web python manage.py makemigrations

shell:
	docker compose -p "$(COMPOSE_PROJECT_NAME)" --env-file "$(ENV_FILE)" -f "$(F_COMPOSE_BASE)" \
	              -f "$(F_COMPOSE_LOCAL)" \
	              -f "$(F_COMPOSE_OVERRIDE)" exec web python manage.py shell

logs:
	docker compose -p "$(COMPOSE_PROJECT_NAME)" --env-file "$(ENV_FILE)" -f "$(F_COMPOSE_BASE)" \
	              -f "$(F_COMPOSE_LOCAL)" \
	              -f "$(F_COMPOSE_OVERRIDE)" logs -f web

restart:
	docker compose -p "$(COMPOSE_PROJECT_NAME)" --env-file "$(ENV_FILE)" -f "$(F_COMPOSE_BASE)" \
	              -f "$(F_COMPOSE_LOCAL)" \
	              -f "$(F_COMPOSE_OVERRIDE)" restart web

# ─────────────────────────────────────────
# REBUILD LOCALE (non interattivo, NON cancella volumi)
# - Re-build dell'immagine web (inclusi gli statici)
# - Applica migrations prima di avviare il nuovo web
# ─────────────────────────────────────────

rebuild:
	docker compose -p "$(COMPOSE_PROJECT_NAME)" --env-file "$(ENV_FILE)" -f "$(F_COMPOSE_BASE)" \
	               -f "$(F_COMPOSE_LOCAL)" \
	               -f "$(F_COMPOSE_OVERRIDE)" build web
	docker compose -p "$(COMPOSE_PROJECT_NAME)" --env-file "$(ENV_FILE)" -f "$(F_COMPOSE_BASE)" \
	               -f "$(F_COMPOSE_LOCAL)" \
	               -f "$(F_COMPOSE_OVERRIDE)" up -d db
	docker compose -p "$(COMPOSE_PROJECT_NAME)" --env-file "$(ENV_FILE)" -f "$(F_COMPOSE_BASE)" \
	               -f "$(F_COMPOSE_LOCAL)" \
	               -f "$(F_COMPOSE_OVERRIDE)" run --rm --no-deps web migrate
	docker compose -p "$(COMPOSE_PROJECT_NAME)" --env-file "$(ENV_FILE)" -f "$(F_COMPOSE_BASE)" \
	               -f "$(F_COMPOSE_LOCAL)" \
	               -f "$(F_COMPOSE_OVERRIDE)" up -d --no-build web

# ─────────────────────────────────────────
# HARD REBUILD (cancella ANCHE i volumi - DB compreso)
# Richiede conferma esplicita.
# ─────────────────────────────────────────

hard-rebuild:
	@echo "⚠ ATTENZIONE: questo comando esegue 'docker compose down -v' e CANCELLA anche i volumi (database, redis, ecc.)."
	@read -p "Sei sicuro di voler procedere? (yes/N): " CONFIRM; \
	if [ "$$CONFIRM" = "yes" ]; then \
	  docker compose -p "$(COMPOSE_PROJECT_NAME)" --env-file "$(ENV_FILE)" -f "$(F_COMPOSE_BASE)" \
	                 -f "$(F_COMPOSE_LOCAL)" \
	                 -f "$(F_COMPOSE_OVERRIDE)" down -v; \
	  docker compose -p "$(COMPOSE_PROJECT_NAME)" --env-file "$(ENV_FILE)" -f "$(F_COMPOSE_BASE)" \
	                 -f "$(F_COMPOSE_LOCAL)" \
	                 -f "$(F_COMPOSE_OVERRIDE)" build; \
	  docker compose -p "$(COMPOSE_PROJECT_NAME)" --env-file "$(ENV_FILE)" -f "$(F_COMPOSE_BASE)" \
	                 -f "$(F_COMPOSE_LOCAL)" \
	                 -f "$(F_COMPOSE_OVERRIDE)" up -d db; \
	  docker compose -p "$(COMPOSE_PROJECT_NAME)" --env-file "$(ENV_FILE)" -f "$(F_COMPOSE_BASE)" \
	                 -f "$(F_COMPOSE_LOCAL)" \
	                 -f "$(F_COMPOSE_OVERRIDE)" run --rm --no-deps web migrate; \
	  docker compose -p "$(COMPOSE_PROJECT_NAME)" --env-file "$(ENV_FILE)" -f "$(F_COMPOSE_BASE)" \
	                 -f "$(F_COMPOSE_LOCAL)" \
	                 -f "$(F_COMPOSE_OVERRIDE)" up -d --no-build web; \
	else \
	  echo "Hard rebuild annullato."; \
	fi
