"""Create a local Keycloak user without putting credentials in shell arguments."""

import argparse
import getpass
import json
import os
import re
import stat
import sys
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener


class ProvisionError(Exception):
    pass


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        return None


def instance_config() -> dict[str, str]:
    env_file = Path(__file__).resolve().parents[1] / ".env"
    if not env_file.is_file() or env_file.stat().st_mode & 0o077:
        raise ProvisionError(".env assente o leggibile da altri utenti; ripristina i permessi 0600.")
    values = {}
    for line in env_file.read_text().splitlines():
        if line and not line.lstrip().startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            values[key] = value
    required = ("KEYCLOAK_PUBLIC_URL", "KEYCLOAK_REALM", "KEYCLOAK_ADMIN", "KEYCLOAK_ADMIN_PASSWORD")
    if any(not values.get(key) for key in required):
        raise ProvisionError("Configurazione Keycloak incompleta in .env.")
    if not re.fullmatch(r"[A-Za-z0-9_-]+", values["KEYCLOAK_REALM"]):
        raise ProvisionError("KEYCLOAK_REALM non valido.")
    url = urlsplit(values["KEYCLOAK_PUBLIC_URL"])
    if (
        url.scheme != "http" or url.hostname not in ("127.0.0.1", "localhost")
        or url.username or url.password or url.path not in ("", "/") or url.query or url.fragment
    ):
        raise ProvisionError("Il comando accetta soltanto Keycloak HTTP su loopback.")
    try:
        if not 1 <= url.port <= 65535:
            raise ValueError
    except (TypeError, ValueError):
        raise ProvisionError("Porta Keycloak locale non valida.") from None
    values["KEYCLOAK_PUBLIC_URL"] = values["KEYCLOAK_PUBLIC_URL"].rstrip("/")
    return values


def user_password(path: str | None) -> str:
    if path:
        password_file = Path(path)
        try:
            metadata = password_file.lstat()
        except OSError:
            raise ProvisionError("File password non leggibile.") from None
        if not stat.S_ISREG(metadata.st_mode) or metadata.st_uid != os.getuid() or metadata.st_mode & 0o077:
            raise ProvisionError("Il file password deve appartenere all'utente corrente e avere permessi 0600.")
        try:
            with password_file.open("rb") as stream:
                raw = stream.read(4097)
        except OSError:
            raise ProvisionError("File password non leggibile.") from None
        if len(raw) > 4096:
            raise ProvisionError("File password troppo grande.")
        try:
            password = raw.decode("utf-8").removesuffix("\n").removesuffix("\r")
        except UnicodeDecodeError:
            raise ProvisionError("File password non valido: usa UTF-8.") from None
    else:
        if not sys.stdin.isatty():
            raise ProvisionError("Terminale interattivo richiesto oppure usa --password-file.")
        password = getpass.getpass("Password temporanea: ")
        if password != getpass.getpass("Ripeti password: "):
            raise ProvisionError("Le password non coincidono.")
    if not 12 <= len(password) <= 1024 or "\n" in password or "\r" in password:
        raise ProvisionError("La password temporanea deve avere 12–1024 caratteri su una sola riga.")
    return password


def open_request(opener, request: Request, expected: int, stage: str):
    try:
        response = opener.open(request, timeout=10)
        with response:
            if response.status != expected:
                raise ProvisionError(f"{stage}: risposta HTTP inattesa ({response.status}).")
            return response.headers, response.read(1048577)
    except HTTPError as error:
        if stage == "Creazione utente" and error.code == 409:
            raise ProvisionError("Utente Keycloak già esistente; nessun account sovrascritto.") from None
        raise ProvisionError(f"{stage}: Keycloak ha risposto HTTP {error.code}.") from None
    except (URLError, TimeoutError, OSError):
        raise ProvisionError(f"{stage}: Keycloak locale non raggiungibile.") from None


def admin_access_token(config: dict[str, str], opener) -> str:
    base = config["KEYCLOAK_PUBLIC_URL"]
    token_request = Request(
        f"{base}/realms/master/protocol/openid-connect/token",
        data=urlencode({
            "client_id": "admin-cli", "grant_type": "password",
            "username": config["KEYCLOAK_ADMIN"], "password": config["KEYCLOAK_ADMIN_PASSWORD"],
        }).encode(),
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    _, token_body = open_request(opener, token_request, 200, "Autenticazione amministrativa")
    if len(token_body) > 1048576:
        raise ProvisionError("Risposta token troppo grande.")
    try:
        token = json.loads(token_body)["access_token"]
        if not isinstance(token, str) or not token:
            raise ValueError
    except (ValueError, KeyError, TypeError):
        raise ProvisionError("Risposta token amministrativo non valida.") from None
    return token


def provision(config: dict[str, str], username: str, email: str, password: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9._-]{3,64}", username):
        raise ProvisionError("Username non valido (3–64 lettere, cifre, punto, trattino o underscore).")
    if len(email) > 254 or email.count("@") != 1 or any(char.isspace() for char in email):
        raise ProvisionError("Email non valida.")

    base = config["KEYCLOAK_PUBLIC_URL"]
    realm = config["KEYCLOAK_REALM"]
    opener = build_opener(ProxyHandler({}), NoRedirect())
    token = admin_access_token(config, opener)

    users_path = f"/admin/realms/{realm}/users"
    created = Request(
        f"{base}{users_path}",
        data=json.dumps({"username": username, "email": email, "enabled": True, "emailVerified": False}).encode(),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {token}"},
        method="POST",
    )
    headers, _ = open_request(opener, created, 201, "Creazione utente")
    location = urlsplit(headers.get("Location", ""))
    prefix = f"{users_path}/"
    subject = location.path.removeprefix(prefix) if location.path.startswith(prefix) else ""
    if not re.fullmatch(r"[0-9a-fA-F-]{36}", subject) or location.query or location.fragment:
        raise ProvisionError("Utente creato, ma Keycloak non ha restituito un ID valido; verifica nella Console amministrativa.")

    credential = Request(
        f"{base}{users_path}/{subject}/reset-password",
        data=json.dumps({"type": "password", "value": password, "temporary": True}).encode(),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {token}"},
        method="PUT",
    )
    try:
        open_request(opener, credential, 204, "Password temporanea")
    except ProvisionError as error:
        raise ProvisionError(f"Utente {subject} creato, ma {error}; completa la password in Keycloak. Nessun reset automatico.") from None
    return subject


def main() -> int:
    parser = argparse.ArgumentParser(description="Crea un utente nel Keycloak locale dell'istanza.")
    parser.add_argument("--username", required=True)
    parser.add_argument("--email", required=True)
    parser.add_argument("--password-file", help="File privato 0600; senza questa opzione la password è richiesta da TTY")
    args = parser.parse_args()
    try:
        config = instance_config()
        password = user_password(args.password_file)
        subject = provision(config, args.username, args.email, password)
    except ProvisionError as error:
        print(f"Errore: {error}", file=sys.stderr)
        return 1
    except (OSError, UnicodeError, ValueError):
        print("Errore: input o risposta locale non valida.", file=sys.stderr)
        return 1
    print(f"Utente Keycloak creato. Subject: {subject}. Password temporanea: cambio richiesto al primo accesso.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
