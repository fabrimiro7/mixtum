import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from django.core.exceptions import ImproperlyConfigured

from mixtum_core.plugin_registry import load_plugins


ROOT = Path(__file__).resolve().parents[1]


def manifest(**changes):
    definition = {
        "id": "example",
        "version": "0.1.0",
        "platform_api": "0.1",
        "django_app": "plugins.plugin_example",
        "url_prefix": "api/example/",
        "urlconf": "plugins.plugin_example.urls",
        "console_package": None,
        "required_capabilities": (),
        "required_plugins": (),
    }
    definition.update(changes)
    return SimpleNamespace(PLUGIN=definition)


class PluginCompositionTests(unittest.TestCase):
    def test_top_level_django_app_package_is_supported(self):
        modules = {
            "instance": SimpleNamespace(PLUGINS=("external_probe.manifest",), CAPABILITIES=()),
            "external_probe.manifest": manifest(
                id="external_probe",
                django_app="external_probe",
                url_prefix="api/external-probe/",
                urlconf="external_probe.urls",
            ),
        }
        with patch("mixtum_core.plugin_registry.import_module", side_effect=modules.__getitem__), \
                patch("mixtum_core.plugin_registry.find_spec", return_value=object()):
            plugins = load_plugins("instance")
        self.assertEqual(plugins[0].django_app, "external_probe")

    def test_invalid_or_missing_top_level_app_is_rejected(self):
        for app_name in ("external-probe", "missing_external_probe_package"):
            with self.subTest(app_name=app_name):
                modules = {
                    "instance": SimpleNamespace(PLUGINS=("external_probe.manifest",), CAPABILITIES=()),
                    "external_probe.manifest": manifest(django_app=app_name),
                }
                with patch("mixtum_core.plugin_registry.import_module", side_effect=modules.__getitem__), \
                        patch("mixtum_core.plugin_registry.find_spec", return_value=None):
                    with self.assertRaises(ImproperlyConfigured):
                        load_plugins("instance")

    def test_plugin_namespace_accepts_an_external_distribution(self):
        with tempfile.TemporaryDirectory() as directory:
            package = Path(directory) / "plugins" / "external_probe"
            package.mkdir(parents=True)
            (package / "__init__.py").write_text("PROBE = 'external'\n")
            env = os.environ.copy()
            env["PYTHONPATH"] = directory
            result = subprocess.run(
                [sys.executable, "-c", "from plugins.external_probe import PROBE; assert PROBE == 'external'"],
                cwd=ROOT, env=env, text=True, capture_output=True, timeout=20,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_same_plugin_loads_from_external_checkout(self):
        with tempfile.TemporaryDirectory() as directory:
            external_root = Path(directory) / "checkout"
            instance_root = Path(directory) / "instance"
            shutil.copytree(
                ROOT / "plugins" / "plugin_example",
                external_root / "plugins" / "plugin_example",
                ignore=shutil.ignore_patterns("build", "*.egg-info", "__pycache__", "dist", "node_modules"),
            )
            instance_root.mkdir()
            for package in ("mixtum_core", "base_modules", "mixtum_instance"):
                (instance_root / package).symlink_to(ROOT / package, target_is_directory=True)
            (instance_root / "plugins").mkdir()
            shutil.copyfile(ROOT / "plugins" / "__init__.py", instance_root / "plugins" / "__init__.py")
            (instance_root / "plugins" / "links").symlink_to(ROOT / "plugins" / "links", target_is_directory=True)
            (instance_root / "plugins" / "ticket").symlink_to(ROOT / "plugins" / "ticket", target_is_directory=True)
            (instance_root / "extensions").symlink_to(ROOT / "extensions", target_is_directory=True)
            env = os.environ.copy()
            env.update(
                PYTHONPATH=str(external_root),
                DJANGO_SETTINGS_MODULE="mixtum_core.settings",
                SECRET_KEY="test-only",
                AUTH_MODE="django",
                USE_S3="0",
            )
            code = """
import os
from pathlib import Path
import django
from django.apps import apps
from django.core.management import call_command
from django.urls import resolve
from plugins.plugin_example import manifest
assert Path(manifest.__file__).resolve().is_relative_to(Path(os.environ['EXTERNAL_ROOT']).resolve())
django.setup()
call_command('check', verbosity=0)
assert apps.is_installed('plugins.plugin_example')
assert resolve('/api/plugin-example/examples/')
"""
            env["EXTERNAL_ROOT"] = str(external_root)
            result = subprocess.run(
                [sys.executable, "-c", code], cwd=instance_root, env=env, text=True, capture_output=True, timeout=30,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_default_composition_keeps_existing_app_and_url(self):
        plugins = load_plugins("mixtum_instance.composition")
        self.assertEqual([(plugin.id, plugin.django_app, plugin.url_prefix) for plugin in plugins], [
            ("plugin_example", "plugins.plugin_example", "api/plugin-example/"),
            ("links", "plugins.links", "api/plugin-links/"),
            ("ticket", "plugins.ticket", "api/plugin-ticket/"),
            ("demo_support", "extensions.demo_support", "api/demo-support/"),
        ])

    def test_missing_requirement_and_incompatible_api_fail_before_start(self):
        for changes in (
            {"required_capabilities": ("storage",)},
            {"required_plugins": ("ticket",)},
            {"platform_api": "2.0"},
            {"url_prefix": "api/workspace/"},
        ):
            with self.subTest(changes=changes):
                modules = {
                    "instance": SimpleNamespace(PLUGINS=("example.manifest",), CAPABILITIES=()),
                    "example.manifest": manifest(**changes),
                }
                with patch("mixtum_core.plugin_registry.import_module", side_effect=modules.__getitem__):
                    with self.assertRaises(ImproperlyConfigured):
                        load_plugins("instance")

    def test_extension_requires_ticket(self):
        modules = {
            "instance": SimpleNamespace(PLUGINS=("extensions.demo_support.manifest",), CAPABILITIES=()),
        }
        from extensions.demo_support import manifest as extension_manifest
        modules["extensions.demo_support.manifest"] = extension_manifest
        with patch("mixtum_core.plugin_registry.import_module", side_effect=modules.__getitem__):
            with self.assertRaisesRegex(ImproperlyConfigured, "missing capabilities.*ticket"):
                load_plugins("instance")

    def test_duplicate_plugin_id_fails_before_start(self):
        modules = {
            "instance": SimpleNamespace(PLUGINS=("one", "two"), CAPABILITIES=()),
            "one": manifest(),
            "two": manifest(url_prefix="api/another/"),
        }
        with patch("mixtum_core.plugin_registry.import_module", side_effect=modules.__getitem__):
            with self.assertRaisesRegex(ImproperlyConfigured, "duplicate plugin"):
                load_plugins("instance")

    def test_empty_instance_does_not_install_or_expose_plugin(self):
        env = os.environ.copy()
        env.update(
            DJANGO_SETTINGS_MODULE="mixtum_core.settings",
            MIXTUM_COMPOSITION_MODULE="tests.fixtures.empty_composition",
            SECRET_KEY="test-only-secret",
            POSTGRES_HOST="",
            AUTH_MODE="django",
            USE_S3="0",
        )
        code = """
import django
django.setup()
from django.apps import apps
from django.urls import Resolver404, resolve
assert not apps.is_installed('plugins.plugin_example')
assert not apps.is_installed('plugins.links')
assert not apps.is_installed('plugins.ticket')
assert not apps.is_installed('extensions.demo_support')
try:
    resolve('/api/plugin-example/examples/')
except Resolver404:
    pass
else:
    raise AssertionError('disabled plugin URL remains exposed')
try:
    resolve('/api/plugin-links/links/')
except Resolver404:
    pass
else:
    raise AssertionError('disabled Links URL remains exposed')
try:
    resolve('/api/plugin-ticket/tickets/')
except Resolver404:
    pass
else:
    raise AssertionError('disabled Ticket URL remains exposed')
try:
    resolve('/api/demo-support/summary/')
except Resolver404:
    pass
else:
    raise AssertionError('disabled extension URL remains exposed')
"""
        result = subprocess.run(
            [sys.executable, "-c", code], cwd=ROOT, env=env, text=True, capture_output=True, timeout=20,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_extension_can_be_disabled_without_disabling_ticket(self):
        env = os.environ.copy()
        env.update(
            DJANGO_SETTINGS_MODULE="mixtum_core.settings",
            MIXTUM_COMPOSITION_MODULE="tests.fixtures.no_extension_composition",
            SECRET_KEY="test-only-secret",
            POSTGRES_HOST="",
            AUTH_MODE="django",
            USE_S3="0",
        )
        code = """
import django
django.setup()
from django.apps import apps
from django.urls import Resolver404, resolve
assert apps.is_installed('plugins.ticket')
assert not apps.is_installed('extensions.demo_support')
assert resolve('/api/plugin-ticket/tickets/')
try:
    resolve('/api/demo-support/summary/')
except Resolver404:
    pass
else:
    raise AssertionError('disabled extension URL remains exposed')
"""
        result = subprocess.run(
            [sys.executable, "-c", code], cwd=ROOT, env=env, text=True, capture_output=True, timeout=20,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_disabling_plugin_leaves_existing_tables_and_data(self):
        with tempfile.TemporaryDirectory() as directory:
            env = os.environ.copy()
            env.update(
                AUTH_MODE="django",
                POSTGRES_HOST="",
                SECRET_KEY="test-only-secret",
                USE_S3="0",
                DJANGO_SETTINGS_MODULE="tests.fixtures.sqlite_settings",
                MIXTUM_SQLITE_TEST_DB=str(Path(directory) / "instance.sqlite3"),
            )
            create = """
import django
django.setup()
from django.core.management import call_command
call_command('migrate', verbosity=0)
from base_modules.user_manager.models import User
from base_modules.workspace.models import Workspace
from plugins.plugin_example.models import ExampleModel
from plugins.links.models import Link
from plugins.ticket.models import ClientCompany, CompanyMembership, Ticket
user = User.objects.create_user('sentinel', 'sentinel@example.test', password='unused')
workspace = Workspace.objects.create(workspace_name='Sentinel')
ExampleModel.objects.create(workspace=workspace, created_by=user, name='Sentinel')
Link.objects.create(workspace=workspace, title='Sentinel', url='https://example.test/sentinel')
company = ClientCompany.objects.create(workspace=workspace, name='Sentinel')
CompanyMembership.objects.create(company=company, user=user)
Ticket.objects.create(workspace=workspace, company=company, requester=user, title='Sentinel', description='Keep')
"""
            created = subprocess.run(
                [sys.executable, "-c", create], cwd=ROOT, env=env, text=True, capture_output=True, timeout=60,
            )
            self.assertEqual(created.returncode, 0, created.stdout + created.stderr)

            env["MIXTUM_COMPOSITION_MODULE"] = "tests.fixtures.empty_composition"
            verify = """
import django
django.setup()
from django.core.management import call_command
from django.db import connection
call_command('migrate', verbosity=0)
with connection.cursor() as cursor:
    cursor.execute('SELECT name FROM plugin_example_examplemodel WHERE name = %s', ['Sentinel'])
    assert cursor.fetchone() == ('Sentinel',)
    cursor.execute('SELECT title FROM links_link WHERE title = %s', ['Sentinel'])
    assert cursor.fetchone() == ('Sentinel',)
    cursor.execute('SELECT title FROM ticket_ticket WHERE title = %s', ['Sentinel'])
    assert cursor.fetchone() == ('Sentinel',)
"""
            disabled = subprocess.run(
                [sys.executable, "-c", verify], cwd=ROOT, env=env, text=True, capture_output=True, timeout=60,
            )
            self.assertEqual(disabled.returncode, 0, disabled.stdout + disabled.stderr)


if __name__ == "__main__":
    unittest.main()
