# syntax=docker/dockerfile:1
FROM python:3.12-slim@sha256:f77ac9e44ae96ef2c90b8053ea08c31f8be030f824196b0ae4db6d462c84e51f

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends libpq5 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt constraints.txt /app/
COPY vendor/wheels/ /wheels/
RUN python -m pip install --no-index --no-deps --find-links=/wheels -r requirements.txt \
    && python -m pip install --find-links=/wheels -c constraints.txt -r requirements.txt \
    && python -m pip check

COPY manage.py /app/manage.py
COPY mixtum_instance/ /app/mixtum_instance/
RUN SECRET_KEY=build-only-placeholder AUTH_MODE=django POSTGRES_HOST= USE_S3=0 \
    python manage.py collectstatic --noinput

RUN useradd --system --uid 10001 --create-home mixtum \
    && mkdir -p /app/media \
    && chown -R 10001:10001 /app
USER 10001:10001

EXPOSE 8000
HEALTHCHECK --interval=10s --timeout=3s --start-period=30s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health/ready/', timeout=2).read()"
