import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
GENERATOR = ROOT / "scripts" / "create-project.sh"


class InstanceTemplateTests(unittest.TestCase):
    def generate(self, destination):
        return subprocess.run(
            ["bash", str(GENERATOR), str(destination)], cwd=ROOT,
            text=True, capture_output=True, timeout=20,
        )

    def test_new_instance_has_configuration_and_no_framework_copy(self):
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "client-one"
            created = self.generate(destination)
            self.assertEqual(created.returncode, 0, created.stdout + created.stderr)
            env = (destination / ".env").read_text()
            self.assertIn(f"MIXTUM_SOURCE={ROOT}", env)
            for name in ("SECRET_KEY", "POSTGRES_PASSWORD", "KEYCLOAK_ADMIN_PASSWORD"):
                self.assertRegex(env, rf"(?m)^{name}=[a-f0-9]{{32,}}$")
            self.assertEqual((destination / ".env").stat().st_mode & 0o777, 0o600)
            self.assertTrue((destination / "mixtum_instance/composition.json").exists())
            self.assertTrue((destination / "console/plugins.ts").exists())
            self.assertTrue((destination / "tools/build-console.sh").exists())
            self.assertTrue((destination / "tools/snapshot-volumes.sh").exists())
            self.assertTrue((destination / "tools/restore-volumes.sh").exists())
            self.assertTrue((destination / "tools/validate-volume-archives.py").exists())
            self.assertTrue((destination / "tools/create-local-keycloak-user.py").exists())
            self.assertTrue((destination / "tools/register-plugin.py").exists())
            self.assertEqual(
                (destination / "keycloak/realm-mixtum.json").read_bytes(),
                (ROOT / "docker/keycloak/realm-mixtum.json").read_bytes(),
            )
            self.assertIn("mixtum-platform-backend==0.1.0", (destination / "requirements.txt").read_text())
            self.assertIn("Django==6.1.1", (destination / "constraints.txt").read_text())
            dockerfile = (destination / "Dockerfile").read_text()
            dockerignore = (destination / ".dockerignore").read_text()
            compose = (destination / "compose.yaml").read_text()
            self.assertIn("COPY vendor/wheels/ /wheels/", dockerfile)
            self.assertNotIn("COPY . ", dockerfile)
            self.assertTrue(dockerignore.startswith("**\n"))
            self.assertNotIn("!.env", dockerignore)
            self.assertIn("context: .", compose)
            self.assertNotIn("context: ${MIXTUM_SOURCE}", compose)
            self.assertIn("./keycloak/realm-mixtum.json", compose)
            self.assertNotIn("${MIXTUM_SOURCE}", compose)
            self.assertNotIn("PYTHONPATH:", compose)
            self.assertNotIn("- .:/instance", compose)
            self.assertIn('command: ["gunicorn"', compose)
            self.assertIn("SERVE_LOCAL_BRANDING_MEDIA", compose)
            self.assertIn("USER 10001:10001", dockerfile)
            self.assertIn("HEALTHCHECK", dockerfile)
            self.assertIn("/health/ready/", dockerfile)
            self.assertIn("python manage.py migrate --noinput", (destination / "Makefile").read_text())
            self.assertEqual(subprocess.run(["make", "check-config"], cwd=destination, capture_output=True).returncode, 0)
            for name in ("mixtum_core", "base_modules", "plugins"):
                self.assertFalse((destination / name).exists())
            self.assertNotIn("SECRET_KEY=", created.stdout)

    def test_web_container_does_not_receive_keycloak_admin_secret(self):
        if shutil.which("docker") is None:
            self.skipTest("Docker Compose CLI non disponibile")
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "client-one"
            self.assertEqual(self.generate(destination).returncode, 0)
            result = subprocess.run(
                ["docker", "compose", "--env-file", ".env", "config", "--format", "json"],
                cwd=destination, text=True, capture_output=True, timeout=20,
                env={key: value for key, value in os.environ.items() if key != "AUTH_MODE"},
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            services = json.loads(result.stdout)["services"]
            web_env = services["web"]["environment"]
            self.assertNotIn("KEYCLOAK_ADMIN_PASSWORD", web_env)
            self.assertNotIn("KEYCLOAK_ADMIN", web_env)
            self.assertNotIn("MIXTUM_SOURCE", web_env)
            self.assertEqual(web_env["AUTH_MODE"], "keycloak")
            self.assertEqual(web_env["KEYCLOAK_API_AUDIENCE"], "mixtum-api")
            self.assertIn("KC_BOOTSTRAP_ADMIN_PASSWORD", services["keycloak"]["environment"])

    def test_incomplete_instance_configuration_is_rejected_before_services(self):
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "client-one"
            self.assertEqual(self.generate(destination).returncode, 0)
            env_file = destination / ".env"
            original = env_file.read_text()
            for name in ("SECRET_KEY", "POSTGRES_PASSWORD", "KEYCLOAK_ADMIN_PASSWORD"):
                with self.subTest(name=name):
                    env_file.write_text(re.sub(rf"(?m)^{name}=.*$", f"{name}=", original))
                    result = subprocess.run(["make", "check-config"], cwd=destination, text=True, capture_output=True)
                    self.assertNotEqual(result.returncode, 0)
                    self.assertIn("Configurazione incompleta", result.stderr)
                    self.assertNotIn("SECRET_KEY=", result.stdout + result.stderr)

    def test_existing_instance_is_never_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "client-one"
            self.assertEqual(self.generate(destination).returncode, 0)
            original = (destination / ".env").read_bytes()
            repeated = self.generate(destination)
            self.assertNotEqual(repeated.returncode, 0)
            self.assertEqual((destination / ".env").read_bytes(), original)

            occupied = Path(directory) / "occupied"
            occupied.mkdir()
            (occupied / "sentinel").write_text("keep")
            self.assertNotEqual(self.generate(occupied).returncode, 0)
            self.assertEqual((occupied / "sentinel").read_text(), "keep")

            empty = Path(directory) / "empty"
            empty.mkdir()
            alias = Path(directory) / "alias"
            alias.symlink_to(empty, target_is_directory=True)
            self.assertNotEqual(self.generate(alias).returncode, 0)
            self.assertEqual(list(empty.iterdir()), [])

    def test_backend_dev_commands_require_prepared_environment(self):
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "client-one"
            self.assertEqual(self.generate(destination).returncode, 0)
            for target in ("plugin-backend-editable", "backend-dev"):
                with self.subTest(target=target):
                    result = subprocess.run(
                        ["make", target], cwd=destination, text=True, capture_output=True,
                    )
                    self.assertNotEqual(result.returncode, 0)
                    self.assertIn("make install-wheels", result.stderr)
                    self.assertFalse((destination / "db.sqlite3").exists())

    def test_two_instances_select_different_plugins_without_changing_mixtum(self):
        with tempfile.TemporaryDirectory() as directory:
            results = []
            for index, plugin in enumerate(("ticket", "links"), start=1):
                destination = Path(directory) / f"client-{index}"
                self.assertEqual(self.generate(destination).returncode, 0)
                self.assertIn(f"COMPOSE_PROJECT_NAME=client-{index}", (destination / ".env").read_text())
                composition = destination / "mixtum_instance/composition.json"
                data = json.loads(composition.read_text())
                data["plugins"] = [plugin]
                composition.write_text(json.dumps(data))
                env = os.environ.copy()
                env.update(
                    SECRET_KEY=next(
                        line.split("=", 1)[1] for line in (destination / ".env").read_text().splitlines()
                        if line.startswith("SECRET_KEY=")
                    ),
                    PYTHONPATH=f"{destination}{os.pathsep}{ROOT}",
                    MIXTUM_INSTANCE_ROOT=str(destination),
                    MIXTUM_COMPOSITION_MODULE="mixtum_instance.composition",
                    DJANGO_SETTINGS_MODULE="mixtum_core.settings",
                    POSTGRES_HOST="",
                    AUTH_MODE="django",
                    USE_S3="0",
                )
                code = """
import django
django.setup()
from django.conf import settings
from django.core.management import call_command
from pathlib import Path
assert settings.BASE_DIR == Path(__import__('os').environ['MIXTUM_INSTANCE_ROOT']).resolve()
assert settings.STATIC_ROOT.is_relative_to(settings.BASE_DIR)
call_command('check', verbosity=0)
print(','.join(plugin.id for plugin in settings.MIXTUM_PLUGINS))
"""
                result = subprocess.run(
                    [sys.executable, "-c", code], cwd=destination, env=env,
                    text=True, capture_output=True, timeout=30,
                )
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                results.append(result.stdout.strip().splitlines()[-1])
            self.assertEqual(results, ["ticket", "links"])


if __name__ == "__main__":
    unittest.main()
