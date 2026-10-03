import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
GENERATOR = ROOT / "scripts/create-plugin.py"


class PluginGeneratorTests(unittest.TestCase):
    def test_generates_ordinary_backend_and_frontend_packages(self):
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "customer_portal"
            result = subprocess.run(
                [sys.executable, str(GENERATOR), "customer_portal", str(destination)],
                text=True, capture_output=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            backend = destination / "backend/mixtum_customer_portal"
            self.assertTrue((backend / "models.py").is_file())
            self.assertTrue((backend / "views.py").is_file())
            self.assertTrue((backend / "serializers.py").is_file())
            self.assertTrue((backend / "migrations/0001_initial.py").is_file())
            self.assertTrue((backend / "tests.py").is_file())
            self.assertIn('"id": "customer_portal"', (backend / "manifest.py").read_text())
            self.assertIn('"django_app": "mixtum_customer_portal"', (backend / "manifest.py").read_text())
            self.assertIn("mixtum-plugin-customer-portal-backend", (destination / "backend/pyproject.toml").read_text())
            package = json.loads((destination / "console/package.json").read_text())
            self.assertEqual(package["name"], "mixtum-plugin-customer-portal-console")
            self.assertIn("customerPortalConsolePlugin", (destination / "console/src/index.ts").read_text())
            self.assertIn("api/customer-portal/items/", (destination / "console/src/item-page.component.ts").read_text())
            for file in destination.rglob("*"):
                if file.is_file():
                    self.assertNotIn("starter_plugin", file.read_text())

    def test_invalid_id_never_creates_destination(self):
        with tempfile.TemporaryDirectory() as directory:
            for plugin_id in ("../escape", "BadName", "bad-name", "a__b", "a_", "a" * 33):
                destination = Path(directory) / "plugin"
                with self.subTest(plugin_id=plugin_id):
                    result = subprocess.run(
                        [sys.executable, str(GENERATOR), plugin_id, str(destination)],
                        text=True, capture_output=True,
                    )
                    self.assertNotEqual(result.returncode, 0)
                    self.assertFalse(destination.exists())

    def test_existing_directory_and_symlink_are_not_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            destination = root / "plugin"
            destination.mkdir()
            sentinel = destination / "keep.txt"
            sentinel.write_text("user data")
            linked = root / "linked"
            linked.symlink_to(destination, target_is_directory=True)
            for target in (destination, linked):
                with self.subTest(target=target):
                    result = subprocess.run(
                        [sys.executable, str(GENERATOR), "safe_plugin", str(target)],
                        text=True, capture_output=True,
                    )
                    self.assertNotEqual(result.returncode, 0)
                    self.assertEqual(sentinel.read_text(), "user data")


if __name__ == "__main__":
    unittest.main()
