#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

fail() { printf 'Errore: %s\n' "$*" >&2; exit 1; }

for prerequisite in docker openssl; do
    command -v "$prerequisite" >/dev/null 2>&1 || fail "Comando richiesto assente: $prerequisite"
done
docker info >/dev/null 2>&1 || fail "Docker non è disponibile. Avvialo e riprova."

read -r -p "Ambiente (local/prod) [local]: " setup_env || true
setup_env="${setup_env:-local}"
[[ "$setup_env" == local ]] || fail "Questo setup prepara solo lo sviluppo locale. La produzione richiede una procedura separata."

base_project_name="$(basename "$ROOT_DIR" | tr '[:upper:]' '[:lower:]' | tr -cs 'a-z0-9' '-' | sed 's/^-*//;s/-*$//')"
[[ -n "$base_project_name" ]] || fail "Impossibile ricavare il nome del progetto."

if [[ -f .env ]]; then
    project_name="$(sed -n 's/^COMPOSE_PROJECT_NAME=//p' .env | sed -n '1p')"
    project_name="${project_name:-$base_project_name}"
    [[ "$project_name" =~ ^[a-z0-9][a-z0-9_-]*$ ]] || fail "COMPOSE_PROJECT_NAME in .env non è valido."
    printf 'Uso la configurazione esistente per %s.\n' "$project_name"
else
    read -r -p "Nome istanza opzionale (es. dev2): " instance_name || true
    instance_name="$(printf '%s' "${instance_name:-}" | tr '[:upper:]' '[:lower:]' | tr -cs 'a-z0-9' '-' | sed 's/^-*//;s/-*$//')"
    project_name="$base_project_name"
    [[ -z "$instance_name" ]] || project_name="${base_project_name}-${instance_name}"

    # List errors must not be mistaken for an absent volume.
    volume_name="${project_name}_postgres_data"
    existing_volume="$(docker volume ls --quiet --filter "name=^${volume_name}$")" || fail "Impossibile verificare i volumi Docker. Nessuna configurazione è stata creata."
    if [[ "$existing_volume" == "$volume_name" ]]; then
        fail "Il volume ${volume_name} esiste ma .env manca. Recupera la configurazione originale oppure scegli un nuovo nome istanza. Nessun dato è stato modificato."
    fi

    [[ -f .env.example ]] || fail ".env.example non trovato."
    secret_key="$(openssl rand -hex 32)"
    database_password="$(openssl rand -hex 24)"
    umask 077
    temp_env="$(mktemp "$ROOT_DIR/.env.XXXXXX")"
    sed -e "s|^SECRET_KEY=.*|SECRET_KEY=${secret_key}|" \
        -e "s|^POSTGRES_PASSWORD=.*|POSTGRES_PASSWORD=${database_password}|" \
        -e "s|^COMPOSE_PROJECT_NAME=.*|COMPOSE_PROJECT_NAME=${project_name}|" \
        -e 's|^USE_S3=.*|USE_S3=0|' \
        .env.example > "$temp_env"
    if ! grep -q '^COMPOSE_PROJECT_NAME=' "$temp_env"; then
        printf '\nCOMPOSE_PROJECT_NAME=%s\n' "$project_name" >> "$temp_env"
    fi
    mv "$temp_env" .env
    printf 'Configurazione locale creata per %s.\n' "$project_name"
fi

configured_secret_key="$(sed -n 's/^SECRET_KEY=//p' .env | sed -n '1p')"
configured_database_password="$(sed -n 's/^POSTGRES_PASSWORD=//p' .env | sed -n '1p')"
[[ -n "$configured_secret_key" && "$configured_secret_key" != changeme && "$configured_secret_key" != django-insecure-default-key ]] || fail "SECRET_KEY manca o usa un valore predefinito. Recupera la configurazione originale; non rigenerare credenziali per un database esistente."
[[ -n "$configured_database_password" ]] || fail "POSTGRES_PASSWORD manca. Recupera la configurazione originale; nessun volume è stato modificato."

compose_args=(-p "$project_name" --env-file "$ROOT_DIR/.env" -f "$ROOT_DIR/docker/docker-compose.yml" -f "$ROOT_DIR/docker/docker-compose.local.yml")
if [[ -f docker/docker-compose.override.yml ]]; then
    compose_args+=(-f "$ROOT_DIR/docker/docker-compose.override.yml")
fi
compose() { docker compose "${compose_args[@]}" "$@"; }

compose config --quiet || fail "Configurazione Compose non valida."
compose build web || fail "Build backend fallita."
compose up -d db || fail "Avvio PostgreSQL fallito."

db_user="$(sed -n 's/^POSTGRES_USER=//p' .env | sed -n '1p')"
db_user="${db_user:-mixtumuser}"
wait_seconds="${DB_WAIT_SECONDS:-60}"
[[ "$wait_seconds" =~ ^[1-9][0-9]*$ ]] || fail "DB_WAIT_SECONDS deve essere un numero positivo."
db_ready=false
for (( attempt=1; attempt<=wait_seconds; attempt++ )); do
    if compose exec -T db pg_isready -U "$db_user" >/dev/null 2>&1; then
        db_ready=true
        break
    fi
    sleep 1
done
[[ "$db_ready" == true ]] || fail "PostgreSQL non è pronto dopo ${wait_seconds}s. Controlla i log del servizio db."

compose run --rm --no-deps web migrate || fail "Migration fallite. Controlla la configurazione del database."
compose up -d web || fail "Avvio backend fallito."

web_wait_seconds="${WEB_WAIT_SECONDS:-30}"
[[ "$web_wait_seconds" =~ ^[1-9][0-9]*$ ]] || fail "WEB_WAIT_SECONDS deve essere un numero positivo."
web_ready=false
for (( attempt=1; attempt<=web_wait_seconds; attempt++ )); do
    if compose exec -T web curl --max-time 3 --silent --show-error --fail --output /dev/null http://127.0.0.1:8000/admin/login/ >/dev/null 2>&1; then
        web_ready=true
        break
    fi
    sleep 1
done
[[ "$web_ready" == true ]] || fail "Il backend non risponde su /admin/login/ dopo ${web_wait_seconds}s. Controlla i log del servizio web."

printf 'Backend locale avviato per %s su http://127.0.0.1:8000.\n' "$project_name"
printf 'Console e Keycloak richiedono una configurazione separata e non sono stati avviati.\n'
