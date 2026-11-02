"""Shared, host-only primitives for the local Keycloak Admin API."""

import json
import os
import re
import stat
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener


MAX_RESPONSE_BYTES = 1024 * 1024
MAX_ENV_BYTES = 64 * 1024


class KeycloakAdminError(Exception):
    pass


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        return None


def admin_opener():
    return build_opener(ProxyHandler({}), NoRedirect())


def instance_config(env_file: Path | None = None) -> dict[str, str]:
    env_file = env_file or Path(__file__).resolve().parents[1] / ".env"
    try:
        metadata = env_file.lstat()
    except OSError:
        raise KeycloakAdminError(".env assente o leggibile da altri utenti; ripristina i permessi 0600.") from None
    if (
        not stat.S_ISREG(metadata.st_mode)
        or metadata.st_uid != os.getuid()
        or metadata.st_mode & 0o077
        or metadata.st_size > MAX_ENV_BYTES
    ):
        raise KeycloakAdminError(".env assente o leggibile da altri utenti; ripristina i permessi 0600.")
    try:
        contents = env_file.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        raise KeycloakAdminError(".env non leggibile o non valido.") from None

    values = {}
    for line in contents.splitlines():
        if line and not line.lstrip().startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            values[key] = value
    required = ("KEYCLOAK_PUBLIC_URL", "KEYCLOAK_REALM", "KEYCLOAK_ADMIN", "KEYCLOAK_ADMIN_PASSWORD")
    if any(not values.get(key) for key in required):
        raise KeycloakAdminError("Configurazione Keycloak incompleta in .env.")
    if not re.fullmatch(r"[A-Za-z0-9_-]+", values["KEYCLOAK_REALM"]):
        raise KeycloakAdminError("KEYCLOAK_REALM non valido.")

    url = urlsplit(values["KEYCLOAK_PUBLIC_URL"])
    if (
        url.scheme != "http"
        or url.hostname not in ("127.0.0.1", "localhost")
        or url.username
        or url.password
        or url.path not in ("", "/")
        or url.query
        or url.fragment
    ):
        raise KeycloakAdminError("Il comando accetta soltanto Keycloak HTTP su loopback.")
    try:
        if not 1 <= url.port <= 65535:
            raise ValueError
    except (TypeError, ValueError):
        raise KeycloakAdminError("Porta Keycloak locale non valida.") from None
    values["KEYCLOAK_PUBLIC_URL"] = values["KEYCLOAK_PUBLIC_URL"].rstrip("/")
    return values


def open_request(
    opener,
    request: Request,
    expected: int,
    stage: str,
    *,
    error_messages: dict[int, str] | None = None,
):
    try:
        response = opener.open(request, timeout=10)
        with response:
            if response.status != expected:
                raise KeycloakAdminError(f"{stage}: risposta HTTP inattesa ({response.status}).")
            body = response.read(MAX_RESPONSE_BYTES + 1)
            if len(body) > MAX_RESPONSE_BYTES:
                raise KeycloakAdminError(f"{stage}: risposta troppo grande.")
            return response.headers, body
    except HTTPError as error:
        if error_messages and error.code in error_messages:
            raise KeycloakAdminError(error_messages[error.code]) from None
        raise KeycloakAdminError(f"{stage}: Keycloak ha risposto HTTP {error.code}.") from None
    except (URLError, TimeoutError, OSError):
        raise KeycloakAdminError(f"{stage}: Keycloak locale non raggiungibile.") from None


def admin_access_token(config: dict[str, str], opener) -> str:
    token_request = Request(
        f"{config['KEYCLOAK_PUBLIC_URL']}/realms/master/protocol/openid-connect/token",
        data=urlencode({
            "client_id": "admin-cli",
            "grant_type": "password",
            "username": config["KEYCLOAK_ADMIN"],
            "password": config["KEYCLOAK_ADMIN_PASSWORD"],
        }).encode(),
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    _, body = open_request(opener, token_request, 200, "Autenticazione amministrativa")
    try:
        token = json.loads(body)["access_token"]
        if not isinstance(token, str) or not token:
            raise ValueError
    except (ValueError, KeyError, TypeError):
        raise KeycloakAdminError("Risposta token amministrativo non valida.") from None
    return token
