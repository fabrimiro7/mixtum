import os
from django.core.exceptions import ImproperlyConfigured

if os.getenv("POSTGRES_HOST"):
    postgres_password = os.getenv("POSTGRES_PASSWORD")
    if not postgres_password:
        raise ImproperlyConfigured("POSTGRES_PASSWORD è obbligatoria quando POSTGRES_HOST è impostato.")
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": os.getenv("POSTGRES_DB", "mixtumdb"),
            "USER": os.getenv("POSTGRES_USER", "mixtumuser"),
            "PASSWORD": postgres_password,
            "HOST": os.getenv("POSTGRES_HOST", "db"),
            "PORT": int(os.getenv("POSTGRES_PORT", "5432")),
            "CONN_MAX_AGE": 60,
        }
    }
else:
    from .base import BASE_DIR  # local fallback
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }
