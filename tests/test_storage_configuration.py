import os
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class StorageConfigurationTests(unittest.TestCase):
    def settings_result(self, **overrides):
        env = os.environ.copy()
        env.update(
            DJANGO_SETTINGS_MODULE="mixtum_core.settings",
            SECRET_KEY="test-only-secret",
            POSTGRES_HOST="",
            AWS_STORAGE_BUCKET_NAME="",
        )
        env.pop("USE_S3", None)
        env.update(overrides)
        return subprocess.run(
            [sys.executable, "-c", "from django.conf import settings; "
             "print(settings.STORAGES['default']['BACKEND']); "
             "print(settings.STORAGES['staticfiles']['BACKEND']); "
             "print(getattr(settings, 'AWS_QUERYSTRING_AUTH', None))"],
            cwd=ROOT, env=env, text=True, capture_output=True, timeout=20,
        )

    def test_local_storage_is_default_without_s3_flag(self):
        result = self.settings_result()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("django.core.files.storage.FileSystemStorage", result.stdout)
        self.assertNotIn("S3Boto3Storage", result.stdout)

    def test_s3_requires_bucket_and_does_not_silently_fall_back(self):
        result = self.settings_result(USE_S3="1")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("AWS_STORAGE_BUCKET_NAME", result.stderr)
        self.assertNotIn("S3Boto3Storage", result.stdout)

    def test_explicit_s3_preserves_local_staticfiles_unless_requested(self):
        result = self.settings_result(USE_S3="1", AWS_STORAGE_BUCKET_NAME="proof-bucket", STATIC_ON_S3="0")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("storages.backends.s3boto3.S3Boto3Storage", result.stdout)
        self.assertIn("django.contrib.staticfiles.storage.StaticFilesStorage", result.stdout)
        self.assertEqual(result.stdout.strip().splitlines()[-1], "True")

    def test_staticfiles_can_be_explicitly_routed_to_s3(self):
        result = self.settings_result(USE_S3="1", AWS_STORAGE_BUCKET_NAME="proof-bucket", STATIC_ON_S3="1")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("storages.backends.s3boto3.S3Boto3Storage", result.stdout)
        self.assertIn("storages.backends.s3boto3.S3StaticStorage", result.stdout)


if __name__ == "__main__":
    unittest.main()
