import importlib.util
import tarfile
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("prepare_mac_handoff", ROOT / "scripts/prepare-mac-handoff.py")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class MacHandoffTests(unittest.TestCase):
    def test_source_filter_keeps_runtime_and_rejects_local_data(self):
        self.assertTrue(MODULE.included("templates/instance/compose.yaml"))
        self.assertTrue(MODULE.included("console/.postcssrc.json"))
        self.assertTrue(MODULE.included("templates/instance/.env.example"))
        for path in (
            ".env", "templates/instance/.env.local", "console/node_modules/a.js",
            "plugins/ticket/.venv/bin/python", "docker/certs/server.pem",
            "media/photo.jpg", "dist/release.tar.gz", "../outside.py",
        ):
            with self.subTest(path=path):
                self.assertFalse(MODULE.included(path))

    def test_archive_includes_current_source_without_secrets_or_local_builds(self):
        with tempfile.TemporaryDirectory() as directory:
            archive = Path(directory) / "source.tar.gz"
            count = MODULE.create_source_archive(archive)
            self.assertGreater(count, 100)
            with tarfile.open(archive, "r:gz") as handle:
                names = {entry.name for entry in handle.getmembers()}
            self.assertIn("mixtum-source/scripts/create-project.sh", names)
            self.assertIn("mixtum-source/scripts/prepare-mac-handoff.py", names)
            self.assertIn("mixtum-source/templates/instance/compose.yaml", names)
            self.assertNotIn("mixtum-source/.env", names)
            self.assertFalse(any("node_modules/" in name or ".venv/" in name for name in names))


if __name__ == "__main__":
    unittest.main()
