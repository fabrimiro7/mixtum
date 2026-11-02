"""Create a local Keycloak user without putting credentials in shell arguments."""

import argparse
import getpass
import json
import os
import re
import stat
import sys
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import ProxyHandler, Request, build_opener

from keycloak_admin import (
    KeycloakAdminError,
    NoRedirect,
    admin_access_token,
    instance_config,
    open_request,
)


ProvisionError = KeycloakAdminError


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
    headers, _ = open_request(
        opener,
        created,
        201,
        "Creazione utente",
        error_messages={409: "Utente Keycloak già esistente; nessun account sovrascritto."},
    )
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
