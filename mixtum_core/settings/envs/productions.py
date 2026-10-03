from django.core.exceptions import ImproperlyConfigured
from ..base import ALLOWED_HOSTS

# A wildcard Host header is never a safe production default.
if not ALLOWED_HOSTS or "*" in ALLOWED_HOSTS:
    raise ImproperlyConfigured("ALLOWED_HOSTS deve contenere host espliciti in produzione.")

DEBUG = False

SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = False  # abilita se dietro proxy con https
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
