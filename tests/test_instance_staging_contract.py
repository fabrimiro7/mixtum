import os
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/verify-instance-staging.py"


class StagingContractTests(unittest.TestCase):
    def test_refuses_execution_outside_ephemeral_ci_runner(self):
        env = os.environ.copy()
        env.pop("GITHUB_ACTIONS", None)
        result = subprocess.run(
            [sys.executable, str(SCRIPT)], cwd=ROOT, env=env,
            text=True, capture_output=True, timeout=10,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("runner CI", result.stderr)
        self.assertNotIn("Traceback", result.stderr)

    def load_module(self):
        spec = importlib.util.spec_from_file_location("verify_instance_staging", SCRIPT)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def staging_context(self, module, root, *, existing_volume=False, volume_error=False, fail_after_restore=False):
        source = root / "mixtum-wheel-proof"
        source.mkdir()
        (source / ".env").write_text("COMPOSE_PROJECT_NAME=mixtum-wheel-proof\n")
        calls = []

        def fake_run(args, **kwargs):
            calls.append(("run", tuple(args)))
            return ""

        def fake_compose(*args, **kwargs):
            calls.append(("compose", tuple(args), kwargs.get("cwd")))
            return ""

        def fake_restore(temp_root, snapshot):
            calls.append(("restore", snapshot))
            target = temp_root / "mixtum-ci-restored"
            target.mkdir()
            return target

        def fake_api(_opener, path, *args, **kwargs):
            if fail_after_restore:
                raise module.StageError("verifica ripristino fallita")
            if path.endswith("/session/"):
                return {"workspaces": [{"id": 7}]}
            return {"title": "Staging A"}

        tool = SimpleNamespace(instance_config=lambda: {
            "KEYCLOAK_PUBLIC_URL": "http://127.0.0.1:8080", "KEYCLOAK_REALM": "mixtum",
        }, NoRedirect=object)
        patches = [
            patch.object(module, "SOURCE", source),
            patch.object(module, "run", side_effect=fake_run),
            patch.object(module, "compose", side_effect=fake_compose),
            patch.object(module, "wait_for"),
            patch.object(module, "keycloak_tool", return_value=tool),
            patch.object(module, "build_opener", return_value=object()),
            patch.object(module, "first_instance", return_value=("ci-client", ("alice", "password", 7, 11))),
            patch.object(module, "browser_login", side_effect=lambda *args: calls.append(("browser", args))),
            patch.object(module, "restore_instance", side_effect=fake_restore),
            patch.object(module, "access_token", return_value="restored-token"),
            patch.object(module, "api_request", side_effect=fake_api),
            patch.object(module.subprocess, "run", return_value=SimpleNamespace(
                returncode=1 if volume_error else 0,
                stdout="mixtum-wheel-proof_postgres_data\n" if existing_volume else "",
            )),
            patch.dict(os.environ, {"GITHUB_ACTIONS": "true"}),
        ]
        return calls, patches

    def test_runner_refuses_preexisting_volume_before_starting_services(self):
        module = self.load_module()
        with tempfile.TemporaryDirectory() as directory:
            calls, patches = self.staging_context(module, Path(directory), existing_volume=True)
            for item in patches:
                item.start()
            try:
                with self.assertRaisesRegex(module.StageError, "Volume staging preesistente"):
                    module.main()
            finally:
                for item in reversed(patches):
                    item.stop()
            self.assertFalse(any(call[0] == "run" for call in calls))

    def test_runner_refuses_volume_inspection_error_before_starting_services(self):
        module = self.load_module()
        with tempfile.TemporaryDirectory() as directory:
            calls, patches = self.staging_context(module, Path(directory), volume_error=True)
            for item in patches:
                item.start()
            try:
                with self.assertRaisesRegex(module.StageError, "Impossibile verificare i volumi"):
                    module.main()
            finally:
                for item in reversed(patches):
                    item.stop()
            self.assertFalse(any(call[0] == "run" for call in calls))

    def test_failure_after_restore_stops_both_projects(self):
        module = self.load_module()
        with tempfile.TemporaryDirectory() as directory:
            calls, patches = self.staging_context(module, Path(directory), fail_after_restore=True)
            for item in patches:
                item.start()
            try:
                with self.assertRaisesRegex(module.StageError, "verifica ripristino fallita"):
                    module.main()
            finally:
                for item in reversed(patches):
                    item.stop()
            self.assertIn(("run", ("make", "prepare")), calls)
            self.assertIn(("run", ("make", "stop")), calls)
            self.assertIn(("browser", ("alice", "password", 7)), calls)
            self.assertTrue(any(call[0] == "restore" for call in calls))
            downs = [call for call in calls if call[0] == "compose" and call[1] == ("down",)]
            self.assertEqual(len(downs), 2)
            self.assertIsNotNone(downs[0][2])
            self.assertIsNone(downs[1][2])

    def test_browser_login_passes_credentials_only_on_stdin(self):
        module = self.load_module()
        calls = []

        def fake_run(args, **kwargs):
            calls.append((args, kwargs))
            return SimpleNamespace(returncode=0, stdout="PASS: login Console con Authorization Code + PKCE\n")

        with patch.object(module.subprocess, "run", side_effect=fake_run):
            module.browser_login("alice", "private-password", 7)
        args, options = calls[0]
        self.assertEqual(args[0], "node")
        self.assertNotIn("private-password", " ".join(args))
        self.assertEqual(json.loads(options["input"]), {
            "username": "alice", "password": "private-password", "workspaceId": 7,
        })
        self.assertTrue(options["capture_output"])

    def test_ci_only_client_has_api_audience_without_changing_product_realm(self):
        module = self.load_module()
        requests = []

        class Response:
            status = 201

            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def read(self, _limit):
                return b""

        class Opener:
            def open(self, request, timeout):
                requests.append(request)
                assert timeout == 10
                return Response()

        tool = SimpleNamespace(admin_access_token=lambda _config, _opener: "admin-token")
        config = {"KEYCLOAK_PUBLIC_URL": "http://127.0.0.1:8080", "KEYCLOAK_REALM": "mixtum"}
        client_id = module.test_client(tool, config, Opener())
        self.assertTrue(client_id.startswith("mixtum-ci-probe-"))
        self.assertEqual(len(requests), 1)
        self.assertEqual(requests[0].get_header("Authorization"), "Bearer admin-token")
        client = json.loads(requests[0].data)
        self.assertEqual(client["clientId"], client_id)
        self.assertTrue(client["directAccessGrantsEnabled"])
        self.assertFalse(client["standardFlowEnabled"])
        self.assertEqual(client["protocolMappers"][0]["config"]["included.custom.audience"], "mixtum-api")
        realm = json.loads((ROOT / "docker/keycloak/realm-mixtum.json").read_text())
        self.assertFalse(any(item.get("directAccessGrantsEnabled") for item in realm["clients"]))


if __name__ == "__main__":
    unittest.main()
