"""Apply the Mixtum login theme to an existing local realm without recreating it."""

import argparse
import json
import re
import sys
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request

from keycloak_admin import (
    KeycloakAdminError,
    admin_access_token,
    admin_opener,
    instance_config,
    open_request,
)


DESIRED_SETTINGS = {
    "displayName": "AI 4 ISO 27001 & NIS2",
    "loginTheme": "mixtum",
    "internationalizationEnabled": True,
    "supportedLocales": ["it", "en"],
    "defaultLocale": "it",
}
CLIENT_NAMES = {
    "mixtum-console": "AI 4 ISO 27001 & NIS2 Console (local development)",
    "mixtum-public": "AI 4 ISO 27001 & NIS2 Public Frontend (local development)",
}


def json_object(body: bytes, stage: str) -> dict:
    try:
        payload = json.loads(body)
    except (UnicodeError, ValueError):
        raise KeycloakAdminError(f"{stage}: risposta JSON non valida.") from None
    if not isinstance(payload, dict):
        raise KeycloakAdminError(f"{stage}: risposta JSON inattesa.")
    return payload


def wait_for_realm(config: dict[str, str], opener, *, seconds: int = 180) -> None:
    url = (
        f"{config['KEYCLOAK_PUBLIC_URL']}/realms/{config['KEYCLOAK_REALM']}"
        "/.well-known/openid-configuration"
    )
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        try:
            with opener.open(Request(url), timeout=3) as response:
                if response.status == 200:
                    response.read(1)
                    return
        except (HTTPError, URLError, TimeoutError, OSError):
            pass
        time.sleep(2)
    raise KeycloakAdminError("Keycloak locale non pronto entro il tempo previsto.")


def available_login_themes(server_info: dict) -> set[str]:
    themes = server_info.get("themes")
    login_themes = themes.get("login") if isinstance(themes, dict) else None
    if not isinstance(login_themes, list):
        raise KeycloakAdminError("Verifica tema: risposta server info inattesa.")
    return {
        item.get("name") for item in login_themes
        if isinstance(item, dict) and isinstance(item.get("name"), str)
    }


def settings_match(representation: dict) -> bool:
    return all(
        set(representation.get(key) or []) == set(value)
        if key == "supportedLocales"
        else representation.get(key) == value
        for key, value in DESIRED_SETTINGS.items()
    )


def reconcile(config: dict[str, str], opener=None) -> bool:
    opener = opener or admin_opener()
    token = admin_access_token(config, opener)
    headers = {"Authorization": f"Bearer {token}"}
    base = config["KEYCLOAK_PUBLIC_URL"]
    realm = config["KEYCLOAK_REALM"]

    _, server_body = open_request(
        opener,
        Request(f"{base}/admin/serverinfo", headers=headers),
        200,
        "Verifica tema",
    )
    if "mixtum" not in available_login_themes(json_object(server_body, "Verifica tema")):
        raise KeycloakAdminError("Tema login 'mixtum' non installato; realm lasciato invariato.")

    realm_url = f"{base}/admin/realms/{realm}"
    _, realm_body = open_request(
        opener,
        Request(realm_url, headers=headers),
        200,
        "Lettura realm",
    )
    representation = json_object(realm_body, "Lettura realm")
    if representation.get("realm") != realm:
        raise KeycloakAdminError("Lettura realm: identificativo inatteso; realm lasciato invariato.")
    changed = False
    if not settings_match(representation):
        updated = dict(representation)
        updated.update(DESIRED_SETTINGS)
        open_request(
            opener,
            Request(
                realm_url,
                data=json.dumps(updated, separators=(",", ":")).encode(),
                headers={**headers, "Content-Type": "application/json"},
                method="PUT",
            ),
            204,
            "Aggiornamento tema realm",
        )
        changed = True

    for client_id, name in CLIENT_NAMES.items():
        _, list_body = open_request(
            opener,
            Request(f"{realm_url}/clients?{urlencode({'clientId': client_id})}", headers=headers),
            200,
            "Lettura client",
        )
        try:
            matches = json.loads(list_body)
        except (UnicodeError, ValueError):
            raise KeycloakAdminError("Lettura client: risposta JSON non valida.") from None
        if not isinstance(matches, list):
            raise KeycloakAdminError("Lettura client: risposta JSON inattesa.")
        match = next((item for item in matches if isinstance(item, dict) and item.get("clientId") == client_id), None)
        if match is None:
            continue  # Older local realms may not yet have both public clients.
        client_key = match.get("id")
        if not isinstance(client_key, str) or not re.fullmatch(r"[A-Za-z0-9-]+", client_key):
            raise KeycloakAdminError("Lettura client: identificativo inatteso.")
        client_url = f"{realm_url}/clients/{client_key}"
        _, client_body = open_request(opener, Request(client_url, headers=headers), 200, "Lettura client")
        client = json_object(client_body, "Lettura client")
        if client.get("clientId") != client_id:
            raise KeycloakAdminError("Lettura client: identificativo inatteso.")
        if client.get("name") == name:
            continue
        client["name"] = name
        open_request(
            opener,
            Request(
                client_url,
                data=json.dumps(client, separators=(",", ":")).encode(),
                headers={**headers, "Content-Type": "application/json"},
                method="PUT",
            ),
            204,
            "Aggiornamento nome client",
        )
        changed = True
    return changed


def main() -> int:
    parser = argparse.ArgumentParser(description="Configura il tema nel Keycloak locale senza ricreare il realm.")
    parser.add_argument("--env-file", type=Path, help="File .env privato; predefinito: .env dell'istanza")
    parser.add_argument("--wait-seconds", type=int, default=180, help=argparse.SUPPRESS)
    args = parser.parse_args()
    try:
        if not 1 <= args.wait_seconds <= 600:
            raise KeycloakAdminError("Timeout di attesa non valido.")
        config = instance_config(args.env_file)
        opener = admin_opener()
        wait_for_realm(config, opener, seconds=args.wait_seconds)
        changed = reconcile(config, opener)
    except KeycloakAdminError as error:
        print(f"Errore: {error}", file=sys.stderr)
        return 1
    except (OSError, UnicodeError, ValueError):
        print("Errore: input o risposta locale non valida.", file=sys.stderr)
        return 1
    print("Branding Keycloak AI 4 ISO 27001 & NIS2 applicato." if changed else "Branding Keycloak AI 4 ISO 27001 & NIS2 già configurato.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
