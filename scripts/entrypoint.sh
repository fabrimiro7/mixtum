#!/usr/bin/env bash
set -euo pipefail

role="${1:-web}"

wait_for_pg() {
    [[ -n "${POSTGRES_HOST:-}" && -n "${POSTGRES_USER:-}" ]] || return 0
    local wait_seconds="${DB_WAIT_SECONDS:-60}"
    [[ "$wait_seconds" =~ ^[1-9][0-9]*$ ]] || { echo 'DB_WAIT_SECONDS deve essere un numero positivo.' >&2; return 1; }
    for (( attempt=1; attempt<=wait_seconds; attempt++ )); do
        if pg_isready -h "$POSTGRES_HOST" -p "${POSTGRES_PORT:-5432}" -U "$POSTGRES_USER" >/dev/null 2>&1; then
            return 0
        fi
        sleep 1
    done
    echo "PostgreSQL non è pronto dopo ${wait_seconds}s." >&2
    return 1
}

case "$role" in
    web)
        wait_for_pg
        exec gunicorn mixtum_core.wsgi:application --bind 0.0.0.0:8000 \
            --workers "${GUNICORN_WORKERS:-3}" --timeout "${GUNICORN_TIMEOUT:-120}"
        ;;
    dev)
        wait_for_pg
        exec python manage.py runserver 0.0.0.0:8000
        ;;
    migrate)
        wait_for_pg
        exec python manage.py migrate --noinput
        ;;
    collectstatic)
        exec python manage.py collectstatic --noinput
        ;;
    worker)
        wait_for_pg
        exec celery -A mixtum_core worker --loglevel="${CELERY_LOG_LEVEL:-INFO}"
        ;;
    beat)
        wait_for_pg
        exec celery -A mixtum_core beat --loglevel="${CELERY_LOG_LEVEL:-INFO}" \
            --scheduler django_celery_beat.schedulers:DatabaseScheduler
        ;;
    *)
        exec "$@"
        ;;
esac
