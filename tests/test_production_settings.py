import os
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class ProductionSettingsTests(unittest.TestCase):
    def settings_result(self, hosts, mode="production"):
        env = os.environ.copy()
        env.update(
            DJANGO_SETTINGS_MODULE="mixtum_core.settings",
            SETTINGS_ENV=mode,
            SECRET_KEY="test-only-production-secret-" * 3,
            POSTGRES_HOST="",
            USE_S3="0",
            AUTH_MODE="django",
        )
        if hosts is None:
            env.pop("ALLOWED_HOSTS", None)
        else:
            env["ALLOWED_HOSTS"] = hosts
        return subprocess.run(
            [sys.executable, "-c", "from django.conf import settings; "
             "print(settings.ALLOWED_HOSTS, settings.DEBUG, "
             "settings.SESSION_COOKIE_SECURE, settings.CSRF_COOKIE_SECURE)"],
            cwd=ROOT, env=env, text=True, capture_output=True, timeout=20,
        )

    def test_production_rejects_missing_or_wildcard_hosts(self):
        for hosts in (None, "", "*", "example.test,*"):
            with self.subTest(hosts=hosts):
                result = self.settings_result(hosts)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("ALLOWED_HOSTS", result.stderr)

    def test_production_accepts_explicit_hosts_and_secure_cookies(self):
        result = self.settings_result("app.example.test,api.example.test")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("app.example.test", result.stdout)
        self.assertIn("False True True", result.stdout)

    def test_local_mode_preserves_explicit_hosts(self):
        result = self.settings_result("127.0.0.1,localhost", mode="local")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("['127.0.0.1', 'localhost']", result.stdout)


if __name__ == "__main__":
    unittest.main()
