import importlib.util
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.parse import parse_qs, urlsplit


ROOT = Path(__file__).resolve().parents[1]
GENERATOR = ROOT / "scripts" / "create-project.sh"
SUBJECT = "5ad12742-a490-43fc-acb3-42b7f26d8e0e"


class Response:
    def __init__(self, status, body=b"", headers=None):
        self.status = status
        self.body = body
        self.headers = headers or {}

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self, limit):
        return self.body[:limit]


class KeycloakOpener:
    def __init__(self, failure=None):
        self.requests = []
        self.failure = failure

    def open(self, request, timeout):
        self.requests.append(request)
        path = urlsplit(request.full_url).path
        assert timeout == 10
        if path.endswith("/realms/master/protocol/openid-connect/token"):
            return Response(200, b'{"access_token":"test-admin-token"}')
        if path.endswith("/admin/realms/mixtum/users"):
            if self.failure == "conflict":
                raise HTTPError(request.full_url, 409, "Conflict", {}, None)
            return Response(201, headers={"Location": f"http://127.0.0.1:8080/admin/realms/mixtum/users/{SUBJECT}"})
        if path.endswith(f"/admin/realms/mixtum/users/{SUBJECT}/reset-password"):
            if self.failure == "reset":
                raise HTTPError(request.full_url, 500, "Failure", {}, None)
            return Response(204)
        raise AssertionError(path)


class LocalKeycloakUserTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.instance = self.root / "client-one"
        result = subprocess.run(
            ["bash", str(GENERATOR), str(self.instance)], cwd=ROOT,
            text=True, capture_output=True, timeout=20,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        script = self.instance / "tools/create-local-keycloak-user.py"
        self.assertTrue(script.exists())
        spec = importlib.util.spec_from_file_location("create_local_keycloak_user", script)
        self.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.module)
        self.password = self.root / "initial-password"
        self.password.write_text("temporary-secret-123\n")
        self.password.chmod(0o600)

    def run_command(self, opener):
        stdout, stderr = io.StringIO(), io.StringIO()
        arguments = [
            "create-local-keycloak-user.py", "--username", "alice", "--email", "alice@example.test",
            "--password-file", str(self.password),
        ]
        with patch.object(self.module, "build_opener", return_value=opener), patch.object(sys, "argv", arguments), \
                patch.object(sys, "stdout", stdout), patch.object(sys, "stderr", stderr):
            code = self.module.main()
        return code, stdout.getvalue(), stderr.getvalue()

    def test_creates_user_and_temporary_password_without_printing_secrets(self):
        opener = KeycloakOpener()
        code, output, errors = self.run_command(opener)
        self.assertEqual(code, 0, errors)
        self.assertEqual(len(opener.requests), 3)
        token_data = parse_qs(opener.requests[0].data.decode())
        self.assertEqual(token_data["client_id"], ["admin-cli"])
        self.assertEqual(token_data["grant_type"], ["password"])
        self.assertTrue(token_data["password"][0])
        created = json.loads(opener.requests[1].data)
        self.assertEqual(created, {
            "username": "alice", "email": "alice@example.test", "enabled": True, "emailVerified": False,
        })
        self.assertEqual(opener.requests[1].get_header("Authorization"), "Bearer test-admin-token")
        credential = json.loads(opener.requests[2].data)
        self.assertEqual(credential, {"type": "password", "value": "temporary-secret-123", "temporary": True})
        self.assertIn(SUBJECT, output)
        self.assertNotIn("temporary-secret-123", output + errors)
        self.assertNotIn(token_data["password"][0], output + errors)
        self.assertNotIn("test-admin-token", output + errors)

    def test_rejects_nonlocal_url_or_readable_password_file_before_http(self):
        env_file = self.instance / ".env"
        original = env_file.read_text()
        env_file.write_text(original.replace("KEYCLOAK_PUBLIC_URL=http://127.0.0.1:8080", "KEYCLOAK_PUBLIC_URL=http://example.test:8080"))
        opener = KeycloakOpener()
        code, _, errors = self.run_command(opener)
        self.assertEqual(code, 1)
        self.assertIn("loopback", errors)
        self.assertFalse(opener.requests)
        env_file.write_text(original)
        self.password.chmod(0o644)
        code, _, errors = self.run_command(opener)
        self.assertEqual(code, 1)
        self.assertIn("0600", errors)
        self.assertFalse(opener.requests)

    def test_missing_or_non_utf8_password_never_prints_input_bytes(self):
        opener = KeycloakOpener()
        self.password.unlink()
        code, _, errors = self.run_command(opener)
        self.assertEqual(code, 1)
        self.assertIn("non leggibile", errors)
        self.password.write_bytes(b"secret-secret-\xff")
        self.password.chmod(0o600)
        code, _, errors = self.run_command(opener)
        self.assertEqual(code, 1)
        self.assertIn("UTF-8", errors)
        self.assertNotIn("\\xff", errors)
        self.assertFalse(opener.requests)

    def test_conflict_never_resets_existing_password(self):
        opener = KeycloakOpener(failure="conflict")
        code, output, errors = self.run_command(opener)
        self.assertEqual(code, 1)
        self.assertEqual(len(opener.requests), 2)
        self.assertIn("già esistente", errors)
        self.assertNotIn("temporary-secret-123", output + errors)

    def test_failed_password_step_reports_partial_creation_without_deletion(self):
        opener = KeycloakOpener(failure="reset")
        code, output, errors = self.run_command(opener)
        self.assertEqual(code, 1)
        self.assertEqual(len(opener.requests), 3)
        self.assertIn(SUBJECT, errors)
        self.assertIn("completa la password", errors)
        self.assertNotIn("temporary-secret-123", output + errors)


if __name__ == "__main__":
    unittest.main()
