import json
import importlib.util
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]


class PluginRegistrationTests(unittest.TestCase):
    def prepare(self, root: Path, *, generated=True):
        instance = root / "instance"
        result = subprocess.run(["bash", str(ROOT / "scripts/create-project.sh"), str(instance)],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        plugin = root / "external-plugin"
        if generated:
            result = subprocess.run([sys.executable, str(ROOT / "scripts/create-plugin.py"),
                                     "inventory_portal", str(plugin)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
        else:
            shutil.copytree(ROOT / "tests/fixtures/external_probe", plugin)
        return instance, plugin

    def register(self, instance: Path, plugin: Path):
        return subprocess.run(["make", "plugin-register", f"PLUGIN_SOURCE={plugin}"], cwd=instance,
                              capture_output=True, text=True)

    def test_registers_generated_plugin_in_ordinary_instance_files(self):
        with tempfile.TemporaryDirectory() as directory:
            instance, plugin = self.prepare(Path(directory))
            result = self.register(instance, plugin)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("mixtum-plugin-inventory-portal-backend==0.1.0",
                          (instance / "requirements.txt").read_text())
            self.assertIn('"inventory_portal": "mixtum_inventory_portal.manifest"',
                          (instance / "mixtum_instance/composition.py").read_text())
            self.assertIn("inventory_portal", json.loads(
                (instance / "mixtum_instance/composition.json").read_text())["plugins"])
            console = (instance / "console/plugins.ts").read_text()
            self.assertIn("from 'mixtum-plugin-inventory-portal-console'", console)
            self.assertIn("  inventoryPortalConsolePlugin,", console)
            self.assertFalse((instance / "db.sqlite3").exists())

            paths = [instance / name for name in (
                "requirements.txt", "mixtum_instance/composition.py",
                "mixtum_instance/composition.json", "console/plugins.ts",
            )]
            before = [path.read_bytes() for path in paths]
            repeated = self.register(instance, plugin)
            self.assertNotEqual(repeated.returncode, 0)
            self.assertEqual(before, [path.read_bytes() for path in paths])

    def test_registers_external_fixture(self):
        with tempfile.TemporaryDirectory() as directory:
            instance, plugin = self.prepare(Path(directory), generated=False)
            result = self.register(instance, plugin)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("@mixtum/plugin-external-probe-console",
                          (instance / "console/plugins.ts").read_text())
            self.assertIn("external_probe", json.loads(
                (instance / "mixtum_instance/composition.json").read_text())["plugins"])

    def test_mismatched_metadata_and_symlink_leave_instance_unchanged(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            instance, plugin = self.prepare(root)
            requirements = instance / "requirements.txt"
            original = requirements.read_bytes()
            package = plugin / "console/package.json"
            data = json.loads(package.read_text())
            data["version"] = "9.9.9"
            package.write_text(json.dumps(data))
            self.assertNotEqual(self.register(instance, plugin).returncode, 0)
            self.assertEqual(requirements.read_bytes(), original)
            package.unlink()
            package.symlink_to(ROOT / "templates/plugin/console/package.json")
            self.assertNotEqual(self.register(instance, plugin).returncode, 0)
            self.assertEqual(requirements.read_bytes(), original)

    def test_write_failure_restores_the_original_files(self):
        with tempfile.TemporaryDirectory() as directory:
            instance, plugin = self.prepare(Path(directory))
            spec = importlib.util.spec_from_file_location(
                "register_plugin", ROOT / "templates/instance/tools/register-plugin.py",
            )
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            paths = [instance / name for name in (
                "requirements.txt", "mixtum_instance/composition.py",
                "mixtum_instance/composition.json", "console/plugins.ts",
            )]
            original = [path.read_bytes() for path in paths]
            actual_replace = module.os.replace
            calls = 0

            def interrupted_replace(source, destination):
                nonlocal calls
                calls += 1
                if calls == 2:
                    raise OSError("simulated write failure")
                return actual_replace(source, destination)

            with patch.object(module.os, "replace", side_effect=interrupted_replace):
                with self.assertRaisesRegex(OSError, "simulated write failure"):
                    module.register(instance, plugin)
            self.assertEqual(original, [path.read_bytes() for path in paths])


if __name__ == "__main__":
    unittest.main()
