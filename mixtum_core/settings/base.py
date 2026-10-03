from pathlib import Path
import os
from django.core.exceptions import ImproperlyConfigured

from mixtum_core.plugin_registry import load_plugins

BASE_DIR = Path(os.environ.get("MIXTUM_INSTANCE_ROOT", Path(__file__).resolve().parents[2])).resolve()
SECRET_KEY = os.environ.get("SECRET_KEY", "")
if not SECRET_KEY or SECRET_KEY in {"changeme", "django-insecure-default-key"}:
    raise ImproperlyConfigured("SECRET_KEY deve essere impostata con un valore non predefinito.")
DEBUG = False

ALLOWED_HOSTS = [h.strip() for h in os.environ.get("ALLOWED_HOSTS", "*").split(",") if h.strip()]
CSRF_TRUSTED_ORIGINS = [o.strip() for o in os.environ.get("CSRF_TRUSTED_ORIGINS", "").split(",") if o.strip()]
CORS_ALLOWED_ORIGINS = [
    o.strip() for o in os.environ.get("CORS_ALLOWED_ORIGINS", "").split(",") if o.strip()
]
CORS_ALLOW_CREDENTIALS = os.environ.get("CORS_ALLOW_CREDENTIALS", "1").lower() in ("1", "true", "yes")
from corsheaders.defaults import default_headers
CORS_ALLOW_HEADERS = list(default_headers) + [
    "x-workspace-id",
]
REMOTE_API = os.environ.get("REMOTE_API", "1").lower() in ("1", "true", "yes")

LANGUAGE_CODE = "it-it"
TIME_ZONE = os.getenv("TIME_ZONE", "Europe/Rome")
USE_I18N = True
USE_TZ = True

JWT_SECRET_KEY = os.environ.get("JWT_SECRET_KEY", SECRET_KEY)

INSTALLED_APPS = [
    # Django
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.sites",

    # Third-party
    "storages",
    "rest_framework",
    "django_celery_results",
    "django_celery_beat",
    "allauth",
    "allauth.account",
    "allauth.headless",
    "allauth.socialaccount",
    "allauth.socialaccount.providers.google",
    "corsheaders",

    # Project apps
    "base_modules.user_manager",
    "base_modules.mailer",
    "base_modules.key_manager",
    "base_modules.branding",
    "base_modules.workspace",
    "base_modules.attachment",
    "base_modules.the_watcher",
    "base_modules.integrations.messaging",

    # Integrations
    "base_modules.integrations.notifications",
    "base_modules.integrations.automation",
]
MIXTUM_COMPOSITION_MODULE = os.environ.get("MIXTUM_COMPOSITION_MODULE", "mixtum_instance.composition")
MIXTUM_PLUGINS = load_plugins(MIXTUM_COMPOSITION_MODULE)
INSTALLED_APPS.extend(plugin.django_app for plugin in MIXTUM_PLUGINS)
SITE_ID = int(os.getenv("SITE_ID", "1"))

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "allauth.account.middleware.AccountMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "mixtum_core.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "mixtum_core.wsgi.application"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"


# -------------------------------------------------------------------
# Twilio WhatsApp Integration
# -------------------------------------------------------------------
from .twilio_conf import *
