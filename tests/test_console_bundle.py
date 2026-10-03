import io
import os
import subprocess
import sys
import tarfile
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class ConsoleBundleTests(unittest.TestCase):
    def test_bundle_contains_only_frontend_inputs(self):
        with tempfile.TemporaryDirectory() as directory:
            bundle = Path(directory) / "mixtum-console-0.1.0.tar.gz"
            result = subprocess.run(
                [sys.executable, str(ROOT / "scripts/package-console-bundle.py"), str(bundle)],
                text=True, capture_output=True, timeout=30,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            with tarfile.open(bundle, "r:gz") as archive:
                names = set(archive.getnames())
                self.assertEqual(archive.extractfile("BUNDLE_VERSION").read(), b"0.1.0\n")
                self.assertIn("console/package-lock.json", names)
                self.assertIn("plugins/ticket/console/src/index.ts", names)
                self.assertNotIn("console/node_modules", names)
                self.assertFalse(any(name.endswith(".env") for name in names))
                self.assertFalse(any("backend" in name or "migrations" in name for name in names))
                self.assertTrue(all(member.isfile() for member in archive))

    def test_instance_rejects_unsafe_bundle_before_npm(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            instance = root / "instance"
            created = subprocess.run(
                ["bash", str(ROOT / "scripts/create-project.sh"), str(instance)],
                text=True, capture_output=True, timeout=20,
            )
            self.assertEqual(created.returncode, 0, created.stderr)
            bundle = root / "unsafe.tar.gz"
            with tarfile.open(bundle, "w:gz") as archive:
                data = b"bad"
                member = tarfile.TarInfo("../outside")
                member.size = len(data)
                archive.addfile(member, io.BytesIO(data))
            env = os.environ.copy()
            env.update(CONSOLE_BUNDLE=str(bundle), MIXTUM_SOURCE="/not-a-checkout")
            result = subprocess.run(
                ["bash", str(instance / "tools/build-console.sh"), str(instance)],
                env=env, text=True, capture_output=True, timeout=20,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("non consentito", result.stderr)
            self.assertNotIn("npm ci", result.stdout + result.stderr)
            self.assertFalse((root / "outside").exists())

    def test_add_package_requires_bundle_and_rejects_linked_tarball(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            instance = root / "instance"
            self.assertEqual(subprocess.run(
                ["bash", str(ROOT / "scripts/create-project.sh"), str(instance)],
                capture_output=True, timeout=20,
            ).returncode, 0)
            archive = root / "plugin.tgz"
            archive.write_bytes(b"not used")
            linked = root / "linked.tgz"
            linked.symlink_to(archive)
            script = instance / "tools/build-console.sh"
            for env, package in (({}, archive), ({"CONSOLE_BUNDLE": "missing.tar.gz"}, linked)):
                with self.subTest(package=package):
                    result = subprocess.run(
                        ["bash", str(script), "--add-package", str(instance), str(package)],
                        env={**os.environ, **env}, text=True, capture_output=True, timeout=20,
                    )
                    self.assertNotEqual(result.returncode, 0)
                    self.assertFalse((instance / "console/package-lock.json").exists())
                    self.assertFalse((instance / "console/vendor").exists())

    def test_add_package_rejects_incomplete_instance_manifests(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            instance = root / "instance"
            self.assertEqual(subprocess.run(
                ["bash", str(ROOT / "scripts/create-project.sh"), str(instance)],
                capture_output=True, timeout=20,
            ).returncode, 0)
            bundle = root / "console.tar.gz"
            self.assertEqual(subprocess.run(
                [sys.executable, str(ROOT / "scripts/package-console-bundle.py"), str(bundle)],
                capture_output=True, timeout=20,
            ).returncode, 0)
            (instance / "console/package.json").write_text("{}")
            package = root / "plugin.tgz"
            package.write_bytes(b"not used")
            result = subprocess.run(
                ["bash", str(instance / "tools/build-console.sh"), "--add-package", str(instance), str(package)],
                env={**os.environ, "CONSOLE_BUNDLE": str(bundle)},
                text=True, capture_output=True, timeout=20,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse((instance / "console/package-lock.json").exists())

    def test_dev_requires_plugin_source_and_valid_port_before_npm(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            instance = root / "instance"
            self.assertEqual(subprocess.run(
                ["bash", str(ROOT / "scripts/create-project.sh"), str(instance)],
                capture_output=True, timeout=20,
            ).returncode, 0)
            plugin = root / "plugin"
            plugin.mkdir()
            (plugin / "package.json").write_text('{"name":"test"}')
            script = instance / "tools/build-console.sh"
            for source, port in ((root / "missing", "4200"), (plugin, "0"), (plugin, "not-a-port")):
                with self.subTest(source=source, port=port):
                    result = subprocess.run(
                        ["bash", str(script), "--dev", str(instance), str(source)],
                        env={**os.environ, "CONSOLE_DEV_PORT": port}, text=True, capture_output=True, timeout=20,
                    )
                    self.assertNotEqual(result.returncode, 0)
                    self.assertNotIn("npm ci", result.stdout + result.stderr)
                    self.assertFalse((instance / "console/package-lock.json").exists())


if __name__ == "__main__":
    unittest.main()
