import os
import io
import subprocess
import tempfile
import tarfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
GENERATOR = ROOT / "scripts" / "create-project.sh"


class VolumeSnapshotTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.instance = self.root / "client-one"
        created = subprocess.run(
            ["bash", str(GENERATOR), str(self.instance)],
            cwd=ROOT, text=True, capture_output=True, timeout=20,
        )
        self.assertEqual(created.returncode, 0, created.stderr)
        self.bin = self.root / "bin"
        self.bin.mkdir()
        self.log = self.root / "docker.log"
        docker = self.bin / "docker"
        docker.write_text('''#!/usr/bin/env python3
import io
import os
import sys
import tarfile
from pathlib import Path

args = sys.argv[1:]
with open(os.environ["TEST_DOCKER_LOG"], "a") as log:
    log.write("docker " + " ".join(args) + "\\n")
if args[:2] == ["volume", "inspect"]:
    name = args[2]
    if os.environ.get("TEST_RESTORE_MODE") and "--format" in args and "mixtum.restore.id" in args[-1]:
        marker = Path(os.environ["TEST_FAKE_VOLUMES_DIR"]) / name / ".restore-id"
        if os.environ.get("TEST_WRONG_OWNER"):
            print("someone-else")
        else:
            print(marker.read_text())
        sys.exit(0)
    if os.environ.get("TEST_RESTORE_MODE") and name.startswith("client-two_"):
        if not os.environ.get("TEST_EXISTING_TARGET"):
            sys.exit(1)
    if os.environ.get("TEST_MISSING_VOLUME") == name:
        sys.exit(1)
    print(name)
elif args[:1] == ["ps"]:
    if os.environ.get("TEST_RESTORE_CONTAINERS") and "label=com.docker.compose.project=client-two" in args[-1]:
        print("existing-container")
    elif os.environ.get("TEST_RUNNING_PROJECT") and "label=com.docker.compose.project=" in args[-1]:
        print("running-console")
    elif os.environ.get("TEST_RUNNING_VOLUME") and os.environ["TEST_RUNNING_VOLUME"] in args[-1]:
        print("running-container")
elif args[:1] == ["run"]:
    if os.environ.get("TEST_FAIL_ARCHIVE") and any(
        os.environ["TEST_FAIL_ARCHIVE"] in item for item in args
    ):
        sys.exit(1)
    if "-czf" in args:
        bind = next(item for item in args if item.startswith("type=bind,source="))
        backup = Path(bind.removeprefix("type=bind,source=").split(",target=", 1)[0])
        archive = backup / Path(args[args.index("-czf") + 1]).name
        with tarfile.open(archive, "w:gz") as output:
            content = b"16" if "postgres_data" in archive.name else b"sentinel"
            filename = "PG_VERSION" if "postgres_data" in archive.name else "sentinel.txt"
            if os.environ.get("TEST_UNSAFE_SNAPSHOT") and "media_data" in archive.name:
                filename = "../outside.txt"
            info = tarfile.TarInfo(filename)
            info.size = len(content)
            output.addfile(info, io.BytesIO(content))
    elif "-xzf" in args:
        volume = next(item for item in args if item.startswith("type=volume,source="))
        name = volume.removeprefix("type=volume,source=").split(",target=", 1)[0]
        bind = next(item for item in args if item.startswith("type=bind,source="))
        backup = Path(bind.removeprefix("type=bind,source=").split(",target=", 1)[0])
        archive = backup / Path(args[args.index("-xzf") + 1]).name
        destination = Path(os.environ["TEST_FAKE_VOLUMES_DIR"]) / name
        with tarfile.open(archive, "r:gz") as source:
            source.extractall(destination, filter="data")
elif args[:2] == ["volume", "create"]:
    name = args[-1]
    destination = Path(os.environ["TEST_FAKE_VOLUMES_DIR"]) / name
    destination.mkdir()
    marker = next(item for item in args if item.startswith("mixtum.restore.id="))
    (destination / ".restore-id").write_text(marker.split("=", 1)[1])
    print(name)
''')
        docker.chmod(0o755)

    def run_snapshot(self, target=None, **overrides):
        env = os.environ.copy()
        env.update(PATH=str(self.bin) + os.pathsep + env["PATH"], TEST_DOCKER_LOG=str(self.log))
        env.update(overrides)
        return subprocess.run(
            ["make", "snapshot-volumes", f"SNAPSHOT_DIR={target or self.root / 'snapshot'}"],
            cwd=self.instance, env=env, text=True, capture_output=True, timeout=20,
        )

    def commands(self):
        return self.log.read_text() if self.log.exists() else ""

    def restore_instance(self):
        target = self.root / "client-two"
        created = subprocess.run(
            ["bash", str(GENERATOR), str(target)], cwd=ROOT,
            text=True, capture_output=True, timeout=20,
        )
        self.assertEqual(created.returncode, 0, created.stderr)
        # A restore needs the original secrets; only the Compose identity changes.
        original = (self.instance / ".env").read_text()
        (target / ".env").write_text(original.replace("COMPOSE_PROJECT_NAME=client-one", "COMPOSE_PROJECT_NAME=client-two"))
        return target

    def run_restore(self, instance, snapshot, **overrides):
        env = os.environ.copy()
        volumes = self.root / "fake-volumes"
        volumes.mkdir(exist_ok=True)
        env.update(PATH=str(self.bin) + os.pathsep + env["PATH"], TEST_DOCKER_LOG=str(self.log),
                   TEST_RESTORE_MODE="1", TEST_FAKE_VOLUMES_DIR=str(volumes))
        env.update(overrides)
        return subprocess.run(
            ["make", "restore-volumes", f"SNAPSHOT_DIR={snapshot}"],
            cwd=instance, env=env, text=True, capture_output=True, timeout=20,
        )

    def test_cold_snapshot_contains_three_checked_archives_without_secrets(self):
        target = self.root / "snapshot"
        result = self.run_snapshot(target)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((target / "STATUS").read_text(), "complete\n")
        self.assertEqual((target.stat().st_mode & 0o777), 0o700)
        self.assertEqual((target / "SHA256SUMS").stat().st_mode & 0o777, 0o600)
        manifest = (target / "MANIFEST").read_text()
        self.assertIn("project=client-one", manifest)
        self.assertIn("secrets_included=no", manifest)
        self.assertNotIn("SECRET_KEY", manifest)
        for name in ("postgres_data", "keycloak_data", "media_data"):
            self.assertTrue((target / f"{name}.tar.gz").is_file())
            self.assertIn(f"volume inspect client-one_{name}", self.commands())
            self.assertIn(f"volume=client-one_{name}", self.commands())
        self.assertEqual(self.commands().count("docker run "), 3)
        repeated = self.run_snapshot(target)
        self.assertNotEqual(repeated.returncode, 0)
        self.assertEqual(self.commands().count("docker run "), 3)

    def test_running_or_missing_volume_fails_before_snapshot(self):
        for flag, value in (
            ("TEST_RUNNING_PROJECT", "1"),
            ("TEST_RUNNING_VOLUME", "client-one_postgres_data"),
            ("TEST_MISSING_VOLUME", "client-one_keycloak_data"),
        ):
            with self.subTest(flag=flag):
                self.log.unlink(missing_ok=True)
                target = self.root / flag
                result = self.run_snapshot(target, **{flag: value})
                self.assertNotEqual(result.returncode, 0)
                self.assertFalse(target.exists())
                self.assertNotIn("docker run ", self.commands())

    def test_s3_configuration_fails_before_docker_and_failed_archive_is_marked(self):
        env_file = self.instance / ".env"
        original = env_file.read_text()
        env_file.write_text(original.replace("USE_S3=0", "USE_S3=1"))
        target = self.root / "s3-snapshot"
        rejected = self.run_snapshot(target)
        self.assertNotEqual(rejected.returncode, 0)
        self.assertFalse(target.exists())
        self.assertFalse(self.log.exists())

        env_file.write_text(original)
        target = self.root / "partial"
        failed = self.run_snapshot(target, TEST_FAIL_ARCHIVE="keycloak_data")
        self.assertNotEqual(failed.returncode, 0)
        self.assertEqual((target / "STATUS").read_text(), "incomplete\n")
        self.assertFalse((target / "SHA256SUMS").exists())

    def test_snapshot_rejects_archive_it_cannot_safely_restore(self):
        target = self.root / "unsafe-snapshot"
        result = self.run_snapshot(target, TEST_UNSAFE_SNAPSHOT="1")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual((target / "STATUS").read_text(), "incomplete\n")
        self.assertFalse((target / "SHA256SUMS").exists())

    def test_restore_only_creates_new_project_volumes_after_validating_snapshot(self):
        snapshot = self.root / "snapshot"
        self.assertEqual(self.run_snapshot(snapshot).returncode, 0)
        target = self.restore_instance()
        self.log.unlink()
        result = self.run_restore(target, snapshot)
        self.assertEqual(result.returncode, 0, result.stderr)
        commands = self.commands()
        self.assertIn("docker ps -a --quiet --filter label=com.docker.compose.project=client-two", commands)
        for volume in ("postgres_data", "keycloak_data", "media_data"):
            self.assertIn(f"com.docker.compose.volume={volume} --label mixtum.restore.id=", commands)
            self.assertIn(f"client-two_{volume}\n", commands)
            restored = self.root / "fake-volumes" / f"client-two_{volume}"
            self.assertTrue((restored / ("PG_VERSION" if volume == "postgres_data" else "sentinel.txt")).exists())
        self.assertEqual(commands.count("docker run "), 3)
        self.assertLess(commands.index("docker volume inspect client-two_media_data"), commands.index("docker volume create --label"))

    def test_restore_rejects_existing_target_and_modified_archive_without_writes(self):
        snapshot = self.root / "snapshot"
        self.assertEqual(self.run_snapshot(snapshot).returncode, 0)
        target = self.restore_instance()
        for flag in ("TEST_EXISTING_TARGET", "TEST_RESTORE_CONTAINERS"):
            with self.subTest(flag=flag):
                self.log.unlink(missing_ok=True)
                result = self.run_restore(target, snapshot, **{flag: "1"})
                self.assertNotEqual(result.returncode, 0)
                self.assertNotIn("docker volume create", self.commands())
        with (snapshot / "media_data.tar.gz").open("ab") as archive:
            archive.write(b"tampered")
        self.log.unlink(missing_ok=True)
        result = self.run_restore(target, snapshot)
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(self.log.exists())

    def test_restore_rejects_same_project_and_unsafe_archive(self):
        snapshot = self.root / "snapshot"
        self.assertEqual(self.run_snapshot(snapshot).returncode, 0)
        same = self.run_restore(self.instance, snapshot)
        self.assertNotEqual(same.returncode, 0)
        self.assertNotIn("docker volume create", self.commands())

        target = self.restore_instance()
        archive_path = snapshot / "media_data.tar.gz"
        with tarfile.open(archive_path, "w:gz") as archive:
            content = b"unsafe"
            member = tarfile.TarInfo("../outside.txt")
            member.size = len(content)
            archive.addfile(member, io.BytesIO(content))
        checksums = subprocess.run(
            ["openssl", "dgst", "-sha256", "postgres_data.tar.gz", "keycloak_data.tar.gz", "media_data.tar.gz"],
            cwd=snapshot, text=True, capture_output=True, check=True,
        )
        (snapshot / "SHA256SUMS").write_text(checksums.stdout)
        self.log.unlink(missing_ok=True)
        unsafe = self.run_restore(target, snapshot)
        self.assertNotEqual(unsafe.returncode, 0)
        self.assertFalse(self.log.exists())

    def test_failed_restore_leaves_partial_volumes_for_manual_recovery(self):
        snapshot = self.root / "snapshot"
        self.assertEqual(self.run_snapshot(snapshot).returncode, 0)
        target = self.restore_instance()
        self.log.unlink()
        failed = self.run_restore(target, snapshot, TEST_FAIL_ARCHIVE="keycloak_data")
        self.assertNotEqual(failed.returncode, 0)
        commands = self.commands()
        self.assertIn("com.docker.compose.volume=postgres_data --label mixtum.restore.id=", commands)
        self.assertIn("com.docker.compose.volume=keycloak_data --label mixtum.restore.id=", commands)
        self.assertNotIn("com.docker.compose.volume=media_data --label mixtum.restore.id=", commands)

    def test_restore_refuses_volume_not_owned_by_this_run(self):
        snapshot = self.root / "snapshot"
        self.assertEqual(self.run_snapshot(snapshot).returncode, 0)
        target = self.restore_instance()
        self.log.unlink()
        failed = self.run_restore(target, snapshot, TEST_WRONG_OWNER="1")
        self.assertNotEqual(failed.returncode, 0)
        self.assertIn("docker volume create", self.commands())
        self.assertNotIn("docker run ", self.commands())


if __name__ == "__main__":
    unittest.main()
