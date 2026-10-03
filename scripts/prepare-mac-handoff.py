#!/usr/bin/env python3
"""Package the current, possibly uncommitted checkout for an isolated Mac smoke test."""

import hashlib
import io
import os
import subprocess
import sys
import tarfile
from pathlib import Path, PurePosixPath


ROOT = Path(__file__).resolve().parents[1]
DIRECTORIES = {
    ".agent", ".agents", ".github", "base_modules", "console", "docker",
    "docs", "extensions", "mixtum_core", "mixtum_instance", "packages",
    "plugins", "public_frontend", "scripts", "templates", "tests",
}
ROOT_FILES = {
    ".dockerignore", ".env.example", ".gitignore", ".nvmrc", "AGENTS.md",
    "ARCHITECTURE.md", "DEFINITION_OF_DONE.md", "Dockerfile", "Makefile",
    "README.md", "README_CODEX.md", "REPOSITORY_LAYOUT.md", "SECURITY.md",
    "TESTING.md", "manage.py", "pyproject.toml", "requirements.txt",
    "requirements-baseline.lock",
}
EXCLUDED_PARTS = {
    ".angular", ".git", ".venv", "__pycache__", "build", "certs",
    "coverage", "dist", "logs", "media", "node_modules", "staticfiles", "vendor",
}
EXCLUDED_SUFFIXES = (
    ".db", ".key", ".p12", ".pem", ".sqlite3", ".tgz", ".whl", ".zip",
)
WHEEL_PROJECTS = (".", "plugins/plugin_example", "plugins/links", "plugins/ticket")


def included(name):
    path = PurePosixPath(name)
    parts = path.parts
    if not parts or ".." in parts or path.is_absolute():
        return False
    if parts[0] not in DIRECTORIES and name not in ROOT_FILES:
        return False
    if any(part in EXCLUDED_PARTS for part in parts):
        return False
    if any(part == ".env" or (part.startswith(".env.") and part != ".env.example") for part in parts):
        return False
    if name.endswith(EXCLUDED_SUFFIXES):
        return False
    return True


def source_files():
    result = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
        cwd=ROOT, capture_output=True, check=True,
    )
    names = sorted({os.fsdecode(raw) for raw in result.stdout.split(b"\0") if raw})
    files = []
    for name in names:
        if not included(name):
            continue
        source = ROOT / name
        if not source.exists():  # tracked deletion in the current checkout
            continue
        if source.is_symlink() or not source.is_file():
            raise ValueError(f"Refusing linked or non-regular source: {name}")
        files.append((name, source))
    required = {"scripts/create-project.sh", "templates/instance/compose.yaml", "console/package-lock.json"}
    missing = required - {name for name, _ in files}
    if missing:
        raise ValueError(f"Required source files missing: {', '.join(sorted(missing))}")
    return files


def create_source_archive(output):
    files = source_files()
    with tarfile.open(output, "w:gz") as archive:
        for name, source in files:
            data = source.read_bytes()
            info = tarfile.TarInfo(f"mixtum-source/{name}")
            info.size = len(data)
            info.mode = 0o755 if os.access(source, os.X_OK) else 0o644
            info.mtime = 0
            archive.addfile(info, io.BytesIO(data))
    return len(files)


def run(*args):
    subprocess.run(args, cwd=ROOT, check=True)


def main():
    if len(sys.argv) != 2:
        raise SystemExit("Uso: python3.12 scripts/prepare-mac-handoff.py /percorso/nuova-directory")
    destination = Path(sys.argv[1]).resolve()
    transfer_archive = destination.parent / f"{destination.name}.tar.gz"
    if destination.exists() or transfer_archive.exists():
        raise SystemExit("L'output esiste già: scegli una destinazione nuova.")
    destination.mkdir(parents=True)
    wheelhouse = destination / "wheels"
    wheelhouse.mkdir()
    count = create_source_archive(destination / "mixtum-source.tar.gz")
    for project in WHEEL_PROJECTS:
        run(sys.executable, "-m", "pip", "wheel", "--no-deps", "--no-build-isolation",
            "--wheel-dir", str(wheelhouse), project)
    run(sys.executable, "scripts/package-console-bundle.py", str(destination / "mixtum-console-0.1.0.tar.gz"))
    artifacts = sorted(path for path in destination.rglob("*") if path.is_file())
    with (destination / "SHA256SUMS").open("w", encoding="utf-8") as checksums:
        for artifact in artifacts:
            digest = hashlib.sha256(artifact.read_bytes()).hexdigest()
            checksums.write(f"{digest}  {artifact.relative_to(destination).as_posix()}\n")
    with tarfile.open(transfer_archive, "w:gz") as archive:
        for artifact in sorted(path for path in destination.rglob("*") if path.is_file()):
            archive.add(artifact, arcname=f"{destination.name}/{artifact.relative_to(destination).as_posix()}")
    print(f"Handoff pronto: {destination} ({count} sorgenti, {len(artifacts)} artefatti)")
    print(f"File unico da trasferire: {transfer_archive}")
    print("Segui docs/engineering/mac-handoff.md nello snapshot.")


if __name__ == "__main__":
    main()
