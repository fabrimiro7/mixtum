import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class LinksMigrationTests(unittest.TestCase):
    def test_existing_generic_link_survives_workspace_scope_migration(self):
        with tempfile.TemporaryDirectory() as directory:
            env = os.environ.copy()
            env.update(
                AUTH_MODE="django",
                USE_S3="0",
                SECRET_KEY="test-only-secret",
                POSTGRES_HOST="",
                DJANGO_SETTINGS_MODULE="tests.fixtures.sqlite_settings",
                MIXTUM_SQLITE_TEST_DB=str(Path(directory) / "legacy.sqlite3"),
            )
            create_legacy = """
import django
django.setup()
from django.core.management import call_command
from django.contrib.contenttypes.models import ContentType
from django.db import connection
call_command('migrate', verbosity=0)
call_command('migrate', 'links', '0001', verbosity=0)
content_type = ContentType.objects.create(app_label='legacy', model='object')
with connection.cursor() as cursor:
    cursor.execute('''INSERT INTO links_link
        (title, description, url, label, content_type_id, object_id, created_at, updated_at)
        VALUES (%s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)''',
        ['Sentinel', '', 'https://example.test/legacy', 'altro', content_type.pk, 17])
"""
            result = subprocess.run(
                [sys.executable, "-c", create_legacy], cwd=ROOT, env=env, text=True, capture_output=True, timeout=60,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

            upgrade = """
import django
django.setup()
from django.core.management import call_command
from plugins.links.models import Link
call_command('migrate', 'links', '0002', verbosity=0)
link = Link.objects.get(title='Sentinel')
assert link.workspace_id is None
assert link.object_id == 17
assert link.content_type.app_label == 'legacy'
assert Link._meta.db_table == 'links_link'
"""
            result = subprocess.run(
                [sys.executable, "-c", upgrade], cwd=ROOT, env=env, text=True, capture_output=True, timeout=60,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
