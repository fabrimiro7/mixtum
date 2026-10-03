import os
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class RequiredSecretsTests(unittest.TestCase):
    def settings_result(self, **overrides):
        env = os.environ.copy()
        env.update(DJANGO_SETTINGS_MODULE="mixtum_core.settings", POSTGRES_HOST="", USE_S3="0")
        for name, value in overrides.items():
            if value is None:
                env.pop(name, None)
            else:
                env[name] = value
        return subprocess.run(
            [sys.executable, "-c", "from django.conf import settings; print(settings.SECRET_KEY)"],
            cwd=ROOT, env=env, text=True, capture_output=True, timeout=20,
        )

    def test_missing_or_placeholder_django_key_fails_closed(self):
        for value in (None, "", "changeme", "django-insecure-default-key"):
            with self.subTest(value=value):
                result = self.settings_result(SECRET_KEY=value)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("SECRET_KEY", result.stderr)
                self.assertNotIn("django-insecure-default-key", result.stdout)

    def test_postgres_requires_explicit_password(self):
        result = self.settings_result(SECRET_KEY="test-only-secret", POSTGRES_HOST="db", POSTGRES_PASSWORD=None)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("POSTGRES_PASSWORD", result.stderr)
        self.assertNotIn("mixtumpassword", result.stdout + result.stderr)

    def test_sqlite_without_postgres_password_is_still_supported(self):
        result = self.settings_result(SECRET_KEY="test-only-secret", POSTGRES_HOST="", POSTGRES_PASSWORD=None)
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
