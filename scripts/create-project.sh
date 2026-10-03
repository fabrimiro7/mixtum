#!/usr/bin/env bash
set -euo pipefail

source_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
template_root="$source_root/templates/instance"
[[ $# -eq 1 ]] || { printf 'Uso: %s /percorso/nuova-istanza\n' "$0" >&2; exit 2; }
command -v openssl >/dev/null 2>&1 || { printf 'openssl non disponibile.\n' >&2; exit 1; }
[[ -f "$template_root/Makefile" ]] || { printf 'Template istanza non trovato.\n' >&2; exit 1; }

destination="${1%/}"
[[ -n "$destination" && "$destination" != "." && "$destination" != "/" ]] || {
    printf 'Scegli una directory di destinazione distinta.\n' >&2; exit 2;
}
parent="$(dirname "$destination")"
[[ -d "$parent" ]] || { printf 'La directory padre non esiste: %s\n' "$parent" >&2; exit 1; }
parent="$(cd "$parent" && pwd -P)"
destination="$parent/$(basename "$destination")"
[[ "$destination" != "$source_root" && "$destination" != "$source_root/"* ]] || {
    printf 'L’istanza deve vivere fuori dal checkout Mixtum.\n' >&2; exit 2;
}
if [[ -e "$destination" ]]; then
    [[ ! -L "$destination" && -d "$destination" && -z "$(ls -A "$destination")" ]] || {
        printf 'La destinazione non è vuota: %s\n' "$destination" >&2; exit 1;
    }
else
    mkdir "$destination"
fi

project_name="$(basename "$destination" | tr '[:upper:]' '[:lower:]' | tr -cs 'a-z0-9' '-' | sed 's/^-*//;s/-*$//')"
[[ -n "$project_name" ]] || { printf 'Nome istanza non valido.\n' >&2; exit 2; }
secret_key="$(openssl rand -hex 32)"
database_password="$(openssl rand -hex 24)"
keycloak_password="$(openssl rand -hex 24)"
umask 077
cp -R "$template_root/." "$destination/"
cp "$source_root/requirements-baseline.lock" "$destination/constraints.txt"
mkdir -p "$destination/tools"
cp "$source_root/scripts/build-instance-console.sh" "$destination/tools/build-console.sh"
mkdir -p "$destination/keycloak"
cp "$source_root/docker/keycloak/realm-mixtum.json" "$destination/keycloak/realm-mixtum.json"
sed -e "s|^COMPOSE_PROJECT_NAME=.*|COMPOSE_PROJECT_NAME=$project_name|" \
    -e "s|^MIXTUM_SOURCE=.*|MIXTUM_SOURCE=$source_root|" \
    -e "s|^SECRET_KEY=.*|SECRET_KEY=$secret_key|" \
    -e "s|^POSTGRES_PASSWORD=.*|POSTGRES_PASSWORD=$database_password|" \
    -e "s|^KEYCLOAK_ADMIN_PASSWORD=.*|KEYCLOAK_ADMIN_PASSWORD=$keycloak_password|" \
    "$destination/.env.example" > "$destination/.env"

printf 'Istanza creata in %s. Configurazione locale in .env (non versionare).\n' "$destination"
printf 'Prossimi comandi: cd %s && make install-wheels WHEELHOUSE=/percorso/wheelhouse && make check\n' "$destination"
printf 'Per la Console: make console-build; per Docker: make stage-wheels WHEELHOUSE=/percorso/wheelhouse\n'
printf 'Per registrare un plugin esterno: make plugin-register PLUGIN_SOURCE=/percorso/plugin\n'
printf 'L’avvio Docker richiede il daemon attivo: make prepare && make up\n'
