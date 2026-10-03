"""Bootstrap regressions; all Docker interactions are simulated."""

import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class BootstrapTests(unittest.TestCase):
    def test_legacy_copy_update_target_is_not_available(self):
        result = subprocess.run(
            ["make", "-f", str(ROOT / "Makefile"), "-n", "update-mixtum"],
            text=True, capture_output=True, cwd=ROOT, timeout=5,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn("git checkout", result.stdout)

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / "mixtum-test"
        (self.root / "scripts").mkdir(parents=True)
        (self.root / "docker").mkdir()
        shutil.copy2(ROOT / "scripts/setup.sh", self.root / "scripts/setup.sh")
        shutil.copy2(ROOT / "scripts/entrypoint.sh", self.root / "scripts/entrypoint.sh")
        shutil.copy2(ROOT / ".env.example", self.root / ".env.example")
        self.bin = Path(self.tmp.name) / "bin"
        self.bin.mkdir()
        self.log = Path(self.tmp.name) / "commands.log"
        self._command("docker", '''#!/usr/bin/env python3
import os, sys
from pathlib import Path
args = sys.argv[1:]
with Path(os.environ['TEST_COMMAND_LOG']).open('a') as log:
    log.write('docker ' + ' '.join(args) + '\\n')
if args[:2] == ['volume', 'ls']:
    if os.environ.get('TEST_VOLUME_ERROR') == '1':
        sys.exit(1)
    if os.environ.get('TEST_VOLUME_EXISTS') == '1':
        print(args[-1].removeprefix('name=^').removesuffix('$'))
    sys.exit(0)
if os.environ.get('TEST_DOCKER_UNAVAILABLE') == '1' and args == ['info']:
    sys.exit(1)
if os.environ.get('TEST_DOCKER_FAIL_AT') and os.environ['TEST_DOCKER_FAIL_AT'] in ' '.join(args):
    sys.exit(1)
sys.exit(0)
''')
        for name in ("python", "gunicorn", "celery", "pg_isready"):
            self._command(name, f"#!/bin/sh\nprintf '%s %s\\n' '{name}' \"$*\" >> \"$TEST_COMMAND_LOG\"\n")

    def _command(self, name, content):
        path = self.bin / name
        path.write_text(content)
        path.chmod(0o755)

    def _run(self, script, answers="", **variables):
        env = os.environ.copy()
        env.update(PATH=str(self.bin) + os.pathsep + env["PATH"], TEST_COMMAND_LOG=str(self.log), DB_WAIT_SECONDS="1")
        env.update(variables)
        return subprocess.run(["bash", str(self.root / "scripts" / script)], input=answers,
                              text=True, capture_output=True, cwd=self.root, env=env, timeout=15)

    def _commands(self):
        return self.log.read_text() if self.log.exists() else ""

    def test_missing_env_existing_volume_stops_before_writes_or_services(self):
        result = self._run("setup.sh", "local\n\n", TEST_VOLUME_EXISTS="1")
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((self.root / ".env").exists())
        commands = self._commands()
        self.assertIn("volume ls --quiet --filter name=^mixtum-test_postgres_data$", commands)
        self.assertNotIn("compose", commands)
        self.assertNotIn("volume rm", commands)

    def test_new_instance_does_not_reuse_old_volume(self):
        result = self._run("setup.sh", "local\nother\n")
        self.assertEqual(result.returncode, 0, result.stderr)
        config = (self.root / ".env").read_text()
        self.assertIn("COMPOSE_PROJECT_NAME=mixtum-test-other", config)
        self.assertIn("USE_S3=0", config)
        self.assertIn("volume ls --quiet --filter name=^mixtum-test-other_postgres_data$", self._commands())
        self.assertIn("web migrate", self._commands())
        self.assertNotIn("volume rm", self._commands())
        self.assertNotIn("down", self._commands())
        self.assertNotIn("changeme", result.stdout + result.stderr)
        self.assertNotIn("mixtumpassword", result.stdout + result.stderr)

    def test_existing_env_is_unchanged(self):
        existing = "COMPOSE_PROJECT_NAME=mixtum-test\nPOSTGRES_USER=test\nPOSTGRES_PASSWORD=private-sentinel\nSECRET_KEY=existing-secret\n"
        (self.root / ".env").write_text(existing)
        result = self._run("setup.sh", "local\n", TEST_VOLUME_EXISTS="1")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((self.root / ".env").read_text(), existing)
        self.assertNotIn("private-sentinel", result.stdout + result.stderr)

    def test_docker_unavailable_never_creates_env(self):
        result = self._run("setup.sh", TEST_DOCKER_UNAVAILABLE="1")
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((self.root / ".env").exists())
        self.assertEqual(self._commands().strip(), "docker info")

    def test_volume_lookup_error_stops_before_creating_env(self):
        result = self._run("setup.sh", "local\n\n", TEST_VOLUME_ERROR="1")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Impossibile verificare", result.stderr)
        self.assertFalse((self.root / ".env").exists())
        self.assertNotIn("compose", self._commands())

    def test_build_and_migration_failures_do_not_start_web(self):
        for failure in ("build web", "web migrate"):
            with self.subTest(failure=failure):
                self.log.unlink(missing_ok=True)
                (self.root / ".env").write_text("COMPOSE_PROJECT_NAME=mixtum-test\nPOSTGRES_PASSWORD=test-password\nSECRET_KEY=test-secret\n")
                result = self._run("setup.sh", "local\n", TEST_DOCKER_FAIL_AT=failure)
                self.assertNotEqual(result.returncode, 0)
                self.assertNotIn("up -d web", self._commands())

    def test_database_timeout_is_bounded(self):
        (self.root / ".env").write_text("COMPOSE_PROJECT_NAME=mixtum-test\nPOSTGRES_PASSWORD=test-password\nSECRET_KEY=test-secret\n")
        result = self._run("setup.sh", "local\n", TEST_DOCKER_FAIL_AT="pg_isready")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("non è pronto", result.stderr)
        self.assertNotIn("web migrate", self._commands())

    def test_web_http_timeout_does_not_report_success(self):
        (self.root / ".env").write_text("COMPOSE_PROJECT_NAME=mixtum-test\nPOSTGRES_PASSWORD=test-password\nSECRET_KEY=test-secret\n")
        result = self._run("setup.sh", "local\n", WEB_WAIT_SECONDS="1", TEST_DOCKER_FAIL_AT="curl --max-time")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("non risponde", result.stderr)
        self.assertNotIn("Backend locale avviato", result.stdout)
        self.assertIn("up -d web", self._commands())

    def test_existing_env_without_secret_fails_without_mutation(self):
        original = "COMPOSE_PROJECT_NAME=mixtum-test\nPOSTGRES_PASSWORD=private-sentinel\nSECRET_KEY=changeme\n"
        (self.root / ".env").write_text(original)
        result = self._run("setup.sh", "local\n")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("SECRET_KEY", result.stderr)
        self.assertEqual((self.root / ".env").read_text(), original)
        self.assertNotIn("compose", self._commands())
        self.assertNotIn("private-sentinel", result.stdout + result.stderr)

    def test_existing_env_without_database_password_fails_without_mutation(self):
        original = "COMPOSE_PROJECT_NAME=mixtum-test\nPOSTGRES_PASSWORD=\nSECRET_KEY=existing-secret\n"
        (self.root / ".env").write_text(original)
        result = self._run("setup.sh", "local\n")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("POSTGRES_PASSWORD", result.stderr)
        self.assertEqual((self.root / ".env").read_text(), original)
        self.assertNotIn("compose", self._commands())

    def test_entrypoint_web_and_diagnostic_do_not_migrate(self):
        for role in ("web", "dev", "check"):
            with self.subTest(role=role):
                self.log.unlink(missing_ok=True)
                result = self._run("entrypoint.sh", POSTGRES_HOST="db", POSTGRES_USER="test") if role == "web" else self._run_role(role)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertNotIn("migrate", self._commands())
                if role == "check":
                    self.assertNotIn("pg_isready", self._commands())

    def test_entrypoint_database_timeout_and_worker_command(self):
        self._command("pg_isready", "#!/bin/sh\nexit 1\n")
        result = self._run_role("web")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("non è pronto", result.stderr)
        self.assertNotIn("gunicorn", self._commands())
        self._command("pg_isready", "#!/bin/sh\nexit 0\n")
        self.log.unlink(missing_ok=True)
        result = self._run_role("worker")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("celery -A mixtum_core worker", self._commands())
        self.assertNotIn("autoreload", self._commands())

    def _run_role(self, role):
        env = os.environ.copy()
        env.update(PATH=str(self.bin) + os.pathsep + env["PATH"], TEST_COMMAND_LOG=str(self.log),
                   POSTGRES_HOST="db", POSTGRES_USER="test", DB_WAIT_SECONDS="1")
        args = ["bash", str(self.root / "scripts/entrypoint.sh")]
        args += ["python", "manage.py", "check"] if role == "check" else [role]
        return subprocess.run(args, text=True, capture_output=True, env=env, timeout=5)


if __name__ == "__main__":
    unittest.main()
