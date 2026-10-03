# Loaded only when AUTH_MODE == "keycloak" (see __init__.py)
import os

KEYCLOAK_SERVER_URL = os.getenv("KEYCLOAK_SERVER_URL", "http://localhost:8080")
KEYCLOAK_REALM = os.getenv("KEYCLOAK_REALM", "mixtum")
KEYCLOAK_ISSUER = os.getenv("KEYCLOAK_ISSUER", f"{KEYCLOAK_SERVER_URL}/realms/{KEYCLOAK_REALM}")
KEYCLOAK_API_AUDIENCE = os.getenv("KEYCLOAK_API_AUDIENCE", "")
KEYCLOAK_JWKS_URL = os.getenv("KEYCLOAK_JWKS_URL", f"{KEYCLOAK_SERVER_URL}/realms/{KEYCLOAK_REALM}/protocol/openid-connect/certs")
