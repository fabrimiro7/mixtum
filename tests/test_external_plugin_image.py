import importlib.util
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/verify-external-plugin.py"


class ExternalPluginImageTests(unittest.TestCase):
    def load_module(self):
        spec = importlib.util.spec_from_file_location("verify_external_plugin", SCRIPT)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_generated_plugin_is_staged_and_checked_in_image(self):
        module = self.load_module()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            checkout = root / "checkout"
            (checkout / "backend").mkdir(parents=True)
            instance = root / "instance"
            instance.mkdir()
            (instance / "requirements.txt").write_text(
                "mixtum-platform-backend==0.1.0\nmixtum-plugin-inventory-portal-backend==0.1.0\n",
            )
            base = root / "base"
            base.mkdir()
            (base / "mixtum_platform_backend-0.1.0-py3-none-any.whl").write_bytes(b"wheel")
            calls = []

            def fake_run(*args, **kwargs):
                calls.append((args, kwargs))
                if "wheel" in args and "--wheel-dir" in args:
                    (root / "wheels/mixtum_plugin_inventory_portal_backend-0.1.0-py3-none-any.whl").write_bytes(b"plugin-wheel")
                if args[:3] == ("docker", "build", "--quiet"):
                    return "sha256:" + "a" * 64
                if args[:2] == ("docker", "run") and "-c" in args:
                    return "/usr/local/lib/python3.12/site-packages/mixtum_inventory_portal/__init__.py"
                return ""

            with patch.object(module, "run", side_effect=fake_run):
                module.verify_backend_image(checkout, instance, root, base, "inventory_portal", "mixtum_inventory_portal")

            self.assertIn("mixtum-plugin-inventory-portal-backend==0.1.0",
                          (instance / "requirements.txt").read_text())
            self.assertTrue((root / "wheels/mixtum_platform_backend-0.1.0-py3-none-any.whl").is_file())
            self.assertTrue(any(args[:2] == ("make", "stage-wheels") and kwargs.get("cwd") == instance
                                for args, kwargs in calls))
            image_runs = [args for args, _ in calls if args[:2] == ("docker", "run")]
            self.assertEqual(len(image_runs), 3)
            self.assertTrue(all("sha256:" + "a" * 64 in args for args in image_runs))
            self.assertTrue(any("mixtum_inventory_portal.tests" in args for args in image_runs))

    def test_rejects_symlink_wheel_before_staging(self):
        module = self.load_module()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            checkout = root / "checkout"
            checkout.mkdir()
            instance = root / "instance"
            instance.mkdir()
            base = root / "base"
            base.mkdir()
            target = root / "target.whl"
            target.write_bytes(b"wheel")
            (base / "linked.whl").symlink_to(target)
            with patch.object(module, "run") as run:
                with self.assertRaisesRegex(RuntimeError, "non-regular wheel"):
                    module.verify_backend_image(checkout, instance, root, base, "probe", "probe")
            run.assert_not_called()


if __name__ == "__main__":
    unittest.main()
