# syntax=docker/dockerfile:1
FROM python:3.12-slim@sha256:f77ac9e44ae96ef2c90b8053ea08c31f8be030f824196b0ae4db6d462c84e51f

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# System deps (per psycopg2, ecc.)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libpq-dev curl postgresql-client \
 && rm -rf /var/lib/apt/lists/*

# Requirements prima per caching
COPY requirements.txt /app/requirements.txt
COPY requirements-baseline.lock /app/requirements-baseline.lock
RUN python -m pip install -r /app/requirements.txt -c /app/requirements-baseline.lock

# Codice
COPY . /app

# Entrypoint eseguibile
RUN chmod +x /app/scripts/entrypoint.sh

# Statici preparati nell'immagine: un container one-shot non li lascerebbe al web.
# I valori qui sono fittizi e non diventano variabili ENV dell'immagine.
RUN SECRET_KEY=build-only-placeholder DEBUG=0 USE_S3=0 \
    python manage.py collectstatic --noinput

EXPOSE 8000
ENTRYPOINT ["/app/scripts/entrypoint.sh"]
