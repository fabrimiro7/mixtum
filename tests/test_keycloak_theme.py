import hashlib
import importlib.util
import io
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.parse import urlsplit


ROOT = Path(__file__).resolve().parents[1]
GENERATOR = ROOT / "scripts/create-project.sh"
THEME = ROOT / "docker/keycloak/themes/mixtum/login"


class Response:
    def __init__(self, status, body=b"", headers=None):
        self.status = status
        self.body = body
        self.headers = headers or {}

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self, limit=-1):
        return self.body if limit < 0 else self.body[:limit]


class ReconcileOpener:
    def __init__(self, realm=None, *, theme_installed=True, realm_missing=False):
        self.realm = realm or {
            "realm": "mixtum",
            "enabled": True,
            "browserFlow": "browser",
            "accountTheme": "keycloak.v2",
            "adminTheme": "keycloak.v2",
            "emailTheme": "keycloak.v2",
            "attributes": {"sentinel": "keep"},
            "clients": [{"clientId": "sentinel-client"}],
        }
        self.theme_installed = theme_installed
        self.realm_missing = realm_missing
        self.clients = {
            "mixtum-console": {"id": "console-id", "clientId": "mixtum-console", "name": "Mixtum Console", "enabled": True},
            "mixtum-public": {"id": "public-id", "clientId": "mixtum-public", "name": "Mixtum Public Frontend", "enabled": True},
        }
        self.requests = []

    def open(self, request, timeout):
        self.requests.append(request)
        self.assert_safe(request, timeout)
        path = urlsplit(request.full_url).path
        method = request.get_method()
        if path.endswith("/realms/master/protocol/openid-connect/token"):
            return Response(200, b'{"access_token":"test-admin-token"}')
        if path == "/admin/serverinfo":
            themes = [{"name": "keycloak.v2"}]
            if self.theme_installed:
                themes.append({"name": "mixtum"})
            return Response(200, json.dumps({"themes": {"login": themes}}).encode())
        if path == "/admin/realms/mixtum" and method == "GET":
            if self.realm_missing:
                raise HTTPError(request.full_url, 404, "Not Found", {}, None)
            return Response(200, json.dumps(self.realm).encode())
        if path == "/admin/realms/mixtum" and method == "PUT":
            self.realm = json.loads(request.data)
            return Response(204)
        if path == "/admin/realms/mixtum/clients" and method == "GET":
            from urllib.parse import parse_qs
            client_id = parse_qs(urlsplit(request.full_url).query).get("clientId", [""])[0]
            return Response(200, json.dumps([self.clients[client_id]] if client_id in self.clients else []).encode())
        for client in self.clients.values():
            if path == f"/admin/realms/mixtum/clients/{client['id']}":
                if method == "GET":
                    return Response(200, json.dumps(client).encode())
                if method == "PUT":
                    client.update(json.loads(request.data))
                    return Response(204)
        raise AssertionError((method, path))

    def assert_safe(self, request, timeout):
        assert timeout == 10
        assert urlsplit(request.full_url).hostname == "127.0.0.1"


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class KeycloakThemeTests(unittest.TestCase):
    def generate(self, destination):
        return subprocess.run(
            ["bash", str(GENERATOR), str(destination)], cwd=ROOT,
            text=True, capture_output=True, timeout=20,
        )

    def load_reconciler(self, instance):
        script = instance / "tools/configure-local-keycloak-theme.py"
        spec = importlib.util.spec_from_file_location("configure_local_keycloak_theme", script)
        module = importlib.util.module_from_spec(spec)
        sys.modules.pop("keycloak_admin", None)
        sys.path.insert(0, str(script.parent))
        try:
            spec.loader.exec_module(module)
        finally:
            sys.path.remove(str(script.parent))
        return module

    def test_canonical_theme_and_realm_are_complete(self):
        expected_hashes = {
            "resources/css/mixtum.css": "71cbece87f0a095c2a7c00c0d754758cbfd95fc40c1c2f486365a52e8f6a3a8c",
            "resources/fonts/TitilliumWeb-Regular.woff2": "861b80b49d2a634d8746e2e45c672309d9ba69a2fdd95da2af034d7a1d09b3f9",
            "resources/fonts/TitilliumWeb-SemiBold.woff2": "f356ff5613e1b6789a47ae3bd6b72fa6fb61d44493811bcb758fb4229b7a8bcb",
            "resources/fonts/TitilliumWeb-Bold.woff2": "9e3162d81ed6681322ab34791660f1b45c79945197e7a7dbb217005b2926caf4",
            "resources/fonts/OFL.txt": "c0562e066174197902a4a10606673d189f067970ef89c6013943b9cf182aadbc",
            "resources/img/mixtum-logo.svg": "c386ebbbdd3a9da4f62cb433d17b02f6c74b130f56510ba92e4282e1fb2a9b3b",
            "resources/img/favicon.ico": "f9102be80297c0529207607be5277b4f90bca89d65988fa1771b91c7894e815f",
        }
        for relative, expected in expected_hashes.items():
            with self.subTest(relative=relative):
                self.assertEqual(sha256(THEME / relative), expected)
        properties = (THEME / "theme.properties").read_text()
        self.assertIn("parent=keycloak.v2", properties)
        self.assertIn("locales=it,en", properties)
        containerfile = (ROOT / "docker/keycloak/Containerfile").read_text()
        self.assertIn("quay.io/keycloak/keycloak:26.7.5", containerfile)
        self.assertIn("@sha256:37dbaf6f0722c9ec246335f36e1ef8b2e6cb960f7c27e0d8c615121a3d475a85", containerfile)
        self.assertNotIn("PASSWORD", containerfile)

        realm = json.loads((ROOT / "docker/keycloak/realm-mixtum.json").read_text())
        self.assertEqual({key: realm[key] for key in (
            "displayName", "loginTheme", "internationalizationEnabled", "supportedLocales", "defaultLocale",
        )}, {
            "displayName": "AI 4 ISO 27001 & NIS2",
            "loginTheme": "mixtum",
            "internationalizationEnabled": True,
            "supportedLocales": ["it", "en"],
            "defaultLocale": "it",
        })
        self.assertNotIn("browserFlow", realm)
        self.assertNotIn("roles", realm)
        self.assertNotIn("groups", realm)
        self.assertEqual([client["name"] for client in realm["clients"]], [
            "AI 4 ISO 27001 & NIS2 Console (local development)",
            "AI 4 ISO 27001 & NIS2 Public Frontend (local development)",
        ])

    def test_generated_instance_contains_the_canonical_keycloak_build(self):
        with tempfile.TemporaryDirectory() as directory:
            instance = Path(directory) / "client-one"
            result = self.generate(instance)
            self.assertEqual(result.returncode, 0, result.stderr)
            source = ROOT / "docker/keycloak"
            for path in source.rglob("*"):
                if path.is_file():
                    relative = path.relative_to(source)
                    self.assertEqual((instance / "keycloak" / relative).read_bytes(), path.read_bytes())
            compose = (instance / "compose.yaml").read_text()
            self.assertIn("context: ./keycloak", compose)
            self.assertIn("dockerfile: Containerfile", compose)
            self.assertNotIn("image: quay.io/keycloak/keycloak", compose)

    def test_reconciler_preserves_unmanaged_realm_data_and_then_is_noop(self):
        with tempfile.TemporaryDirectory() as directory:
            instance = Path(directory) / "client-one"
            self.assertEqual(self.generate(instance).returncode, 0)
            module = self.load_reconciler(instance)
            config = module.instance_config()
            opener = ReconcileOpener()

            self.assertTrue(module.reconcile(config, opener))
            self.assertEqual(opener.realm["attributes"], {"sentinel": "keep"})
            self.assertEqual(opener.realm["clients"], [{"clientId": "sentinel-client"}])
            self.assertEqual(opener.realm["browserFlow"], "browser")
            self.assertEqual(opener.realm["accountTheme"], "keycloak.v2")
            self.assertEqual(opener.realm["adminTheme"], "keycloak.v2")
            self.assertEqual(opener.realm["emailTheme"], "keycloak.v2")
            self.assertEqual({key: opener.realm[key] for key in module.DESIRED_SETTINGS}, module.DESIRED_SETTINGS)
            self.assertEqual([client["name"] for client in opener.clients.values()], [
                "AI 4 ISO 27001 & NIS2 Console (local development)",
                "AI 4 ISO 27001 & NIS2 Public Frontend (local development)",
            ])
            self.assertTrue(all(client["enabled"] for client in opener.clients.values()))
            self.assertEqual([request.get_method() for request in opener.requests].count("PUT"), 3)

            normalized = dict(opener.realm)
            normalized["supportedLocales"] = ["en", "it"]
            second = ReconcileOpener(realm=normalized)
            second.clients = opener.clients
            self.assertFalse(module.reconcile(config, second))
            self.assertNotIn("PUT", [request.get_method() for request in second.requests])

    def test_reconciler_fails_closed_before_reading_realm_when_theme_is_missing(self):
        with tempfile.TemporaryDirectory() as directory:
            instance = Path(directory) / "client-one"
            self.assertEqual(self.generate(instance).returncode, 0)
            module = self.load_reconciler(instance)
            opener = ReconcileOpener(theme_installed=False)
            with self.assertRaisesRegex(module.KeycloakAdminError, "non installato"):
                module.reconcile(module.instance_config(), opener)
            self.assertEqual([urlsplit(request.full_url).path for request in opener.requests], [
                "/realms/master/protocol/openid-connect/token", "/admin/serverinfo",
            ])

    def test_reconciler_reports_missing_realm_without_exposing_secrets(self):
        with tempfile.TemporaryDirectory() as directory:
            instance = Path(directory) / "client-one"
            self.assertEqual(self.generate(instance).returncode, 0)
            module = self.load_reconciler(instance)
            opener = ReconcileOpener(realm_missing=True)
            stdout, stderr = io.StringIO(), io.StringIO()
            with patch.object(module, "admin_opener", return_value=opener), \
                    patch.object(module, "wait_for_realm"), \
                    patch.object(sys, "argv", ["configure-local-keycloak-theme.py"]), \
                    patch.object(sys, "stdout", stdout), patch.object(sys, "stderr", stderr):
                self.assertEqual(module.main(), 1)
            output = stdout.getvalue() + stderr.getvalue()
            env = module.instance_config()
            self.assertIn("HTTP 404", output)
            self.assertNotIn(env["KEYCLOAK_ADMIN_PASSWORD"], output)
            self.assertNotIn("test-admin-token", output)

    def test_shared_config_rejects_nonlocal_url_and_nonprivate_env(self):
        with tempfile.TemporaryDirectory() as directory:
            instance = Path(directory) / "client-one"
            self.assertEqual(self.generate(instance).returncode, 0)
            module = self.load_reconciler(instance)
            env_file = instance / ".env"
            original = env_file.read_text()
            env_file.write_text(original.replace(
                "KEYCLOAK_PUBLIC_URL=http://127.0.0.1:8080",
                "KEYCLOAK_PUBLIC_URL=https://keycloak.example.test",
            ))
            with self.assertRaisesRegex(module.KeycloakAdminError, "loopback"):
                module.instance_config()
            env_file.write_text(original)
            env_file.chmod(0o644)
            with self.assertRaisesRegex(module.KeycloakAdminError, "0600"):
                module.instance_config()


if __name__ == "__main__":
    unittest.main()
