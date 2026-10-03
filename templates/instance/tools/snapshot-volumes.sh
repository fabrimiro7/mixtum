#!/usr/bin/env bash
set -euo pipefail

instance_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
cd "$instance_root"

fail() { printf 'Errore: %s\n' "$*" >&2; exit 1; }
[[ $# -eq 1 ]] || fail "Uso: make snapshot-volumes SNAPSHOT_DIR=/percorso/nuovo-snapshot"
[[ -f .env && -f compose.yaml ]] || fail "Istanza incompleta: .env o compose.yaml assente."

destination="${1%/}"
[[ "$destination" == /* && "$destination" != / && "$destination" != *','* ]] ||
    fail "SNAPSHOT_DIR deve essere un percorso assoluto nuovo, senza virgole."
parent="$(dirname "$destination")"
[[ -d "$parent" ]] || fail "La directory padre dello snapshot non esiste."
parent="$(cd "$parent" && pwd -P)"
name="$(basename "$destination")"
[[ "$name" != . && "$name" != .. ]] || fail "Nome snapshot non valido."
destination="$parent/$name"
[[ ! -e "$destination" && ! -L "$destination" ]] || fail "La destinazione esiste già: $destination"

project="$(sed -n 's/^COMPOSE_PROJECT_NAME=//p' .env | sed -n '1p')"
[[ "$project" =~ ^[a-z0-9][a-z0-9_-]*$ ]] || fail "COMPOSE_PROJECT_NAME non valido in .env."
use_s3="$(sed -n 's/^USE_S3=//p' .env | sed -n '1p' | tr '[:upper:]' '[:lower:]')"
[[ "$use_s3" != 1 && "$use_s3" != true && "$use_s3" != yes ]] ||
    fail "USE_S3 è attivo: serve anche uno snapshot del bucket. Questo comando copre solo i media locali."

command -v docker >/dev/null 2>&1 || fail "Docker non disponibile."
command -v openssl >/dev/null 2>&1 || fail "OpenSSL non disponibile."
command -v python3 >/dev/null 2>&1 || fail "Python 3 non disponibile."
docker info >/dev/null 2>&1 || fail "Docker daemon non disponibile."
docker compose --env-file .env config --quiet || fail "Configurazione Compose non valida."
running_project="$(docker ps --quiet --filter "label=com.docker.compose.project=$project")" ||
    fail "Impossibile verificare i container dell'istanza."
[[ -z "$running_project" ]] || fail "L'istanza $project ha container in esecuzione. Usa make stop prima dello snapshot."

volumes=(postgres_data keycloak_data media_data)
for volume in "${volumes[@]}"; do
    volume_name="${project}_${volume}"
    found="$(docker volume inspect "$volume_name" --format '{{.Name}}')" ||
        fail "Volume $volume_name non trovato; nessuno snapshot creato."
    [[ "$found" == "$volume_name" ]] || fail "Risposta inattesa per il volume $volume_name."
    running="$(docker ps --quiet --filter "volume=$volume_name")" || fail "Impossibile verificare $volume_name."
    [[ -z "$running" ]] || fail "Il volume $volume_name è usato da un container in esecuzione. Ferma l'istanza prima dello snapshot."
done

umask 077
mkdir -m 700 "$destination" || fail "Impossibile creare $destination."
printf 'incomplete\n' > "$destination/STATUS"
printf 'project=%s\ncreated_utc=%s\nvolumes=postgres_data,keycloak_data,media_data\nsecrets_included=no\n' \
    "$project" "$(date -u '+%Y-%m-%dT%H:%M:%SZ')" > "$destination/MANIFEST"

for volume in "${volumes[@]}"; do
    volume_name="${project}_${volume}"
    docker run --rm --network none \
        --mount "type=volume,source=$volume_name,target=/source,readonly" \
        --mount "type=bind,source=$destination,target=/backup" \
        --entrypoint tar postgres:16-alpine \
        -C /source -czf "/backup/${volume}.tar.gz" . ||
        fail "Snapshot di $volume_name fallito. La directory $destination resta marcata incomplete."
    [[ -s "$destination/${volume}.tar.gz" ]] || fail "Archivio vuoto per $volume_name."
done
python3 "$instance_root/tools/validate-volume-archives.py" "$destination" ||
    fail "Archivio non sicuro o non leggibile. La directory resta marcata incomplete."

(
    cd "$destination"
    openssl dgst -sha256 postgres_data.tar.gz keycloak_data.tar.gz media_data.tar.gz > SHA256SUMS
)
printf 'complete\n' > "$destination/STATUS"
printf 'Snapshot cold dei tre volumi creato in %s. .env e configurazione istanza NON sono inclusi.\n' "$destination"
