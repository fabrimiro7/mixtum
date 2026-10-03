"""CI-only: exercise a generated instance against real Compose services and a cold restore."""

import importlib.util
import json
import os
import re
import secrets
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import ProxyHandler, Request, build_opener


ROOT = Path(__file__).resolve().parents[1]
SOURCE = Path("/tmp/mixtum-wheel-proof")
WEB_URL = "http://127.0.0.1:8000"
CONSOLE_URL = "http://127.0.0.1:4200"
MEDIA_SENTINEL = "mixtum-ci-media-sentinel"


class StageError(Exception):
    pass


def run(args, *, cwd=SOURCE, timeout=300):
    result = subprocess.run(args, cwd=cwd, text=True, capture_output=True, timeout=timeout)
    if result.returncode:
        raise StageError(f"Comando fallito ({result.returncode}): {args[0]} {args[1] if len(args) > 1 else ''}")
    return result.stdout.strip()


def compose(*args, cwd=SOURCE, timeout=300):
    return run(["docker", "compose", "--env-file", ".env", *args], cwd=cwd, timeout=timeout)


def wait_for(url, *, seconds=180):
    opener = build_opener(ProxyHandler({}))
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        try:
            with opener.open(url, timeout=3) as response:
                if response.status == 200:
                    return
        except (HTTPError, URLError, TimeoutError, OSError):
            pass
        time.sleep(2)
    raise StageError(f"Servizio non pronto: {url}")


def keycloak_tool(instance):
    path = instance / "tools/create-local-keycloak-user.py"
    spec = importlib.util.spec_from_file_location("ci_keycloak_user", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def json_request(opener, url, *, data=None, token=None, method="GET", expected=200):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    body = json.dumps(data).encode() if data is not None else None
    request = Request(url, data=body, headers=headers, method=method)
    try:
        with opener.open(request, timeout=10) as response:
            if response.status != expected:
                raise StageError(f"HTTP {response.status} invece di {expected} su {method} {url}")
            content = response.read(1048577)
    except HTTPError as error:
        raise StageError(f"HTTP {error.code} invece di {expected} su {method} {url}") from None
    if len(content) > 1048576:
        raise StageError("Risposta HTTP troppo grande")
    return json.loads(content) if content else None


def api_request(opener, path, token=None, workspace=None, expected=200, data=None, method="GET"):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if workspace is not None:
        headers["X-Workspace-Id"] = str(workspace)
    request = Request(
        f"{WEB_URL}{path}",
        data=json.dumps(data).encode() if data is not None else None,
        headers=headers,
        method=method,
    )
    try:
        with opener.open(request, timeout=10) as response:
            status = response.status
            body = response.read(1048577)
    except HTTPError as error:
        status = error.code
        body = b""
    if status != expected:
        raise StageError(f"API {path}: HTTP {status} invece di {expected}")
    return json.loads(body) if body else None


def test_client(tool, config, opener):
    admin_token = tool.admin_access_token(config, opener)
    client_id = "mixtum-ci-probe-" + secrets.token_hex(6)
    json_request(
        opener,
        f"{config['KEYCLOAK_PUBLIC_URL']}/admin/realms/{config['KEYCLOAK_REALM']}/clients",
        token=admin_token,
        method="POST",
        expected=201,
        data={
            "clientId": client_id,
            "enabled": True,
            "protocol": "openid-connect",
            "publicClient": True,
            "standardFlowEnabled": False,
            "directAccessGrantsEnabled": True,
            "serviceAccountsEnabled": False,
            "defaultClientScopes": ["web-origins", "roles", "profile", "email"],
            "protocolMappers": [{
                "name": "ci-api-audience",
                "protocol": "openid-connect",
                "protocolMapper": "oidc-audience-mapper",
                "consentRequired": False,
                "config": {
                    "included.custom.audience": "mixtum-api",
                    "access.token.claim": "true",
                    "id.token.claim": "false",
                },
            }],
        },
    )
    return client_id


def make_user(tool, config, opener, username):
    password = secrets.token_urlsafe(24)
    subject = tool.provision(config, username, f"{username}@example.test", password)
    admin_token = tool.admin_access_token(config, opener)
    # The product tool creates a temporary password. CI clears that requirement
    # only for its isolated direct-grant probe, never in the versioned realm.
    json_request(
        opener,
        f"{config['KEYCLOAK_PUBLIC_URL']}/admin/realms/{config['KEYCLOAK_REALM']}/users/{subject}/reset-password",
        token=admin_token,
        method="PUT",
        expected=204,
        data={"type": "password", "value": password, "temporary": False},
    )
    return subject, password


def access_token(config, opener, client_id, username, password):
    request = Request(
        f"{config['KEYCLOAK_PUBLIC_URL']}/realms/{config['KEYCLOAK_REALM']}/protocol/openid-connect/token",
        data=urlencode({
            "client_id": client_id, "grant_type": "password",
            "username": username, "password": password,
        }).encode(),
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    try:
        with opener.open(request, timeout=10) as response:
            if response.status != 200:
                raise StageError("Token utente non disponibile")
            payload = json.loads(response.read(1048577))
            return payload["access_token"]
    except (HTTPError, URLError, ValueError, KeyError, OSError):
        raise StageError("Token utente non disponibile") from None


def shell(code, *, cwd=SOURCE):
    return compose("run", "--rm", "web", "python", "manage.py", "shell", "-c", code, cwd=cwd)


def create_workspace(name):
    output = shell(
        "from base_modules.workspace.models import Workspace; "
        f"print(Workspace.objects.create(workspace_name={name!r}).pk)"
    )
    return int(output.splitlines()[-1])


def seed_company_and_ticket(workspace_name, subject, title):
    code = (
        "from base_modules.user_manager.models import ExternalIdentity; "
        "from base_modules.workspace.models import Workspace; "
        "from plugins.ticket.models import ClientCompany, CompanyMembership; "
        f"u=ExternalIdentity.objects.get(subject={subject!r}).user; "
        f"w=Workspace.objects.get(workspace_name={workspace_name!r}); "
        f"c=ClientCompany.objects.create(workspace=w,name={title!r}); "
        "CompanyMembership.objects.create(company=c,user=u); print(c.pk)"
    )
    return int(shell(code).splitlines()[-1])


def seed_branding():
    shell(
        "from base_modules.branding.models import BrandingSettings; "
        "from base_modules.workspace.models import Workspace; "
        "BrandingSettings.objects.create(colors={'--ed-blue': '#14532d'}); "
        "BrandingSettings.objects.create(workspace=Workspace.objects.get(workspace_name='CI Alpha'), "
        "colors={'--ed-blue': '#1e3a8a'})"
    )


def first_instance(tool, config, opener):
    api_request(opener, "/api/workspace/session/", expected=401)
    client_id = test_client(tool, config, opener)
    subject_a, password_a = make_user(tool, config, opener, "mixtum-ci-a")
    subject_b, password_b = make_user(tool, config, opener, "mixtum-ci-b")
    token_a = access_token(config, opener, client_id, "mixtum-ci-a", password_a)
    token_b = access_token(config, opener, client_id, "mixtum-ci-b", password_b)
    api_request(opener, "/api/workspace/session/", token="not-a-token", expected=401)
    if api_request(opener, "/api/workspace/session/", token=token_a)["workspaces"]:
        raise StageError("Utente A ha membership prima della concessione")
    if api_request(opener, "/api/workspace/session/", token=token_b)["workspaces"]:
        raise StageError("Utente B ha membership prima della concessione")

    compose("run", "--rm", "web", "python", "manage.py", "grant_workspace_member",
            "--subject", subject_a, "--new-workspace-name", "CI Alpha")
    workspace_a = api_request(opener, "/api/workspace/session/", token=token_a)["workspaces"][0]["id"]
    workspace_b = create_workspace("CI Beta")
    compose("run", "--rm", "web", "python", "manage.py", "grant_workspace_member",
            "--subject", subject_b, "--workspace-id", str(workspace_b))
    seed_branding()
    company_a = seed_company_and_ticket("CI Alpha", subject_a, "Company A")
    company_b = seed_company_and_ticket("CI Beta", subject_b, "Company B")
    ticket_a = api_request(
        opener, "/api/plugin-ticket/tickets/", token_a, workspace_a, 201,
        {"company_id": company_a, "title": "Staging A", "description": "Persist A"}, "POST",
    )["id"]
    ticket_b = api_request(
        opener, "/api/plugin-ticket/tickets/", token_b, workspace_b, 201,
        {"company_id": company_b, "title": "Staging B", "description": "Persist B"}, "POST",
    )["id"]
    api_request(opener, "/api/plugin-ticket/tickets/", token_a, workspace_b, expected=403)
    api_request(opener, f"/api/plugin-ticket/tickets/{ticket_b}/", token_a, workspace_a, expected=404)
    api_request(opener, f"/api/plugin-ticket/tickets/{ticket_a}/", token_b, workspace_b, expected=404)
    if api_request(opener, f"/api/plugin-ticket/tickets/{ticket_a}/", token_a, workspace_a)["title"] != "Staging A":
        raise StageError("Ticket A non leggibile")
    shell(
        "from pathlib import Path; "
        f"Path('/app/media/ci-sentinel.txt').write_text({MEDIA_SENTINEL!r})"
    )
    return client_id, ("mixtum-ci-a", password_a, workspace_a, ticket_a)


def browser_login(username, password, workspace):
    result = subprocess.run(
        ["node", str(ROOT / "console/tools/verify-instance-login.mjs")],
        input=json.dumps({"username": username, "password": password, "workspaceId": workspace}),
        text=True, capture_output=True, cwd=ROOT, timeout=90,
    )
    if result.returncode:
        raise StageError("Login Console via browser non riuscito")
    if "PASS: login Console" not in result.stdout:
        raise StageError("Esito login Console non verificabile")


def restore_instance(temp_root, snapshot):
    target = temp_root / "mixtum-ci-restored"
    run(["bash", str(ROOT / "scripts/create-project.sh"), str(target)], cwd=ROOT, timeout=30)
    source_env = (SOURCE / ".env").read_text()
    old_project = re.search(r"(?m)^COMPOSE_PROJECT_NAME=(.+)$", source_env)
    if old_project is None or old_project.group(1) != "mixtum-wheel-proof":
        raise StageError("Progetto sorgente staging inatteso")
    (target / ".env").write_text(source_env.replace(
        "COMPOSE_PROJECT_NAME=mixtum-wheel-proof", "COMPOSE_PROJECT_NAME=mixtum-ci-restored", 1,
    ))
    (target / ".env").chmod(0o600)
    shutil.copytree(SOURCE / "vendor/wheels", target / "vendor/wheels", dirs_exist_ok=True)
    try:
        run(["make", "restore-volumes", f"SNAPSHOT_DIR={snapshot}"], cwd=target)
        compose("build", "web", cwd=target)
        compose("up", "-d", "db", "keycloak", cwd=target)
        compose("run", "--rm", "web", "python", "manage.py", "migrate", "--check", cwd=target)
        compose("up", "-d", "web", cwd=target)
        wait_for(f"{WEB_URL}/health/ready/")
    except Exception:
        try:
            compose("down", cwd=target)
        except (StageError, OSError, subprocess.TimeoutExpired):
            pass
        raise
    return target


def main():
    if os.environ.get("GITHUB_ACTIONS") != "true" or not SOURCE.is_dir():
        raise StageError("La prova è riservata all'istanza temporanea del runner CI")
    source_env = (SOURCE / ".env").read_text()
    if "COMPOSE_PROJECT_NAME=mixtum-wheel-proof\n" not in source_env:
        raise StageError("Nome progetto staging inatteso")
    # CI must never attach to a previous project's state, even on a reused runner.
    if compose("ps", "-a", "--quiet"):
        raise StageError("Container staging preesistenti")
    volumes = subprocess.run(
        ["docker", "volume", "ls", "--format", "{{.Name}}"],
        text=True, capture_output=True, timeout=10,
    )
    if volumes.returncode:
        raise StageError("Impossibile verificare i volumi Docker")
    existing = set(volumes.stdout.splitlines())
    if any(f"mixtum-wheel-proof_{name}" in existing for name in ("postgres_data", "keycloak_data", "media_data")):
        raise StageError("Volume staging preesistente")

    tool = keycloak_tool(SOURCE)
    config = tool.instance_config()
    opener = build_opener(ProxyHandler({}), tool.NoRedirect())
    try:
        run(["make", "prepare"])
        wait_for(f"{config['KEYCLOAK_PUBLIC_URL']}/realms/{config['KEYCLOAK_REALM']}/.well-known/openid-configuration")
        compose("up", "-d", "web", "console")
        wait_for(f"{WEB_URL}/health/ready/")
        wait_for(f"{CONSOLE_URL}/assets/mixtum-config.json")
        client_id, (username, password, workspace, ticket) = first_instance(tool, config, opener)
        browser_login(username, password, workspace)
        run(["make", "stop"])
        with tempfile.TemporaryDirectory(prefix="mixtum-ci-recovery-") as temporary:
            root = Path(temporary)
            snapshot = root / "snapshot"
            run(["make", "snapshot-volumes", f"SNAPSHOT_DIR={snapshot}"])
            target = None
            try:
                target = restore_instance(root, snapshot)
                restored_token = access_token(config, opener, client_id, username, password)
                session = api_request(opener, "/api/workspace/session/", restored_token)
                if [item["id"] for item in session["workspaces"]] != [workspace]:
                    raise StageError("Membership non recuperata")
                result = api_request(opener, f"/api/plugin-ticket/tickets/{ticket}/", restored_token, workspace)
                if result["title"] != "Staging A":
                    raise StageError("Ticket non recuperato")
                media = compose("run", "--rm", "web", "python", "-c",
                                "from pathlib import Path; print(Path('/app/media/ci-sentinel.txt').read_text())", cwd=target)
                if media.splitlines()[-1] != MEDIA_SENTINEL:
                    raise StageError("Media non recuperati")
                print("PASS: Console PKCE, Keycloak/PostgreSQL reali, due workspace isolati e restore cold di identità, Ticket e media.")
            finally:
                if target is not None:
                    compose("down", cwd=target)
    finally:
        compose("down")


if __name__ == "__main__":
    try:
        main()
    except (StageError, subprocess.TimeoutExpired, OSError, ValueError, KeyError) as error:
        print(f"FAIL staging: {type(error).__name__}: {error}", file=sys.stderr)
        raise SystemExit(1)
