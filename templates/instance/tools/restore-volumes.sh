#!/usr/bin/env bash
set -euo pipefail

instance_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
cd "$instance_root"

fail() { printf 'Errore: %s\n' "$*" >&2; exit 1; }
[[ $# -eq 1 ]] || fail "Uso: make restore-volumes SNAPSHOT_DIR=/percorso/snapshot-completo"
[[ -f .env && -f compose.yaml ]] || fail "Istanza incompleta: .env o compose.yaml assente."

snapshot="${1%/}"
[[ "$snapshot" == /* && -d "$snapshot" && ! -L "$snapshot" ]] ||
    fail "SNAPSHOT_DIR deve essere una directory assoluta esistente, non un symlink."
snapshot="$(cd "$snapshot" && pwd -P)"
[[ -f "$snapshot/STATUS" && "$(<"$snapshot/STATUS")" == complete ]] || fail "Snapshot non completo."
[[ -f "$snapshot/MANIFEST" && -f "$snapshot/SHA256SUMS" ]] || fail "Manifest o checksum mancanti."

project="$(sed -n 's/^COMPOSE_PROJECT_NAME=//p' .env | sed -n '1p')"
source_project="$(sed -n 's/^project=//p' "$snapshot/MANIFEST" | sed -n '1p')"
[[ "$project" =~ ^[a-z0-9][a-z0-9_-]*$ && "$source_project" =~ ^[a-z0-9][a-z0-9_-]*$ ]] ||
    fail "Nome progetto non valido nella destinazione o nello snapshot."
[[ "$project" != "$source_project" ]] || fail "Il restore richiede un progetto distinto da quello dello snapshot."
[[ "$(sed -n 's/^volumes=//p' "$snapshot/MANIFEST" | sed -n '1p')" == postgres_data,keycloak_data,media_data ]] ||
    fail "Manifest dei volumi incompatibile."
use_s3="$(sed -n 's/^USE_S3=//p' .env | sed -n '1p' | tr '[:upper:]' '[:lower:]')"
[[ "$use_s3" != 1 && "$use_s3" != true && "$use_s3" != yes ]] ||
    fail "USE_S3 è attivo: questo restore copre solo i media locali."

command -v docker >/dev/null 2>&1 || fail "Docker non disponibile."
command -v openssl >/dev/null 2>&1 || fail "OpenSSL non disponibile."
command -v python3 >/dev/null 2>&1 || fail "Python 3 non disponibile."

# Validate all input before creating any target volume.
(
    cd "$snapshot"
    openssl dgst -sha256 postgres_data.tar.gz keycloak_data.tar.gz media_data.tar.gz | cmp - SHA256SUMS
) >/dev/null 2>&1 || fail "Checksum degli archivi non valido."
python3 "$instance_root/tools/validate-volume-archives.py" "$snapshot" || fail "Archivio non sicuro o non leggibile."

docker info >/dev/null 2>&1 || fail "Docker daemon non disponibile."
docker compose --env-file .env config --quiet || fail "Configurazione Compose non valida."
containers="$(docker ps -a --quiet --filter "label=com.docker.compose.project=$project")" ||
    fail "Impossibile verificare i container della destinazione."
[[ -z "$containers" ]] || fail "Il progetto $project possiede già container. Scegli una nuova istanza."

volumes=(postgres_data keycloak_data media_data)
for volume in "${volumes[@]}"; do
    volume_name="${project}_${volume}"
    if docker volume inspect "$volume_name" >/dev/null 2>&1; then
        fail "Il volume di destinazione $volume_name esiste già. Nessun dato verrà sovrascritto."
    fi
done

restore_id="$(openssl rand -hex 16)" || fail "Impossibile generare l'identificatore del restore."
for volume in "${volumes[@]}"; do
    volume_name="${project}_${volume}"
    docker volume create \
        --label "com.docker.compose.project=$project" \
        --label "com.docker.compose.volume=$volume" \
        --label "mixtum.restore.id=$restore_id" \
        "$volume_name" >/dev/null || fail "Creazione di $volume_name fallita. Verifica i volumi parziali prima di riprovare."
    owner="$(docker volume inspect "$volume_name" --format '{{ index .Labels "mixtum.restore.id" }}')" ||
        fail "Impossibile verificare la proprietà di $volume_name. Non avviare l'istanza."
    [[ "$owner" == "$restore_id" ]] || fail "Il volume $volume_name non appartiene a questo restore. Nessun dato scritto."
    docker run --rm --network none \
        --mount "type=volume,source=$volume_name,target=/target" \
        --mount "type=bind,source=$snapshot,target=/backup,readonly" \
        --entrypoint tar postgres:16-alpine \
        -C /target -xzf "/backup/${volume}.tar.gz" ||
        fail "Restore di $volume_name fallito. Non avviare l'istanza; verifica i volumi parziali."
done

printf 'Volumi ripristinati nel progetto %s. Verifica .env originale, configurazione, dati e login prima dell’avvio operativo.\n' "$project"
