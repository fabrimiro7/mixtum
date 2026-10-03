"""Check the release boundary of a built Mixtum backend wheel."""

import sys
from pathlib import Path
from zipfile import ZipFile


def verify(wheel_path: Path, repository_root: Path) -> None:
    with ZipFile(wheel_path) as archive:
        names = set(archive.namelist())

    expected = {
        "mixtum_core/__init__.py",
        "mixtum_core/plugin_registry.py",
        "mixtum_core/health.py",
        "mixtum_core/settings/base.py",
        "base_modules/user_manager/models.py",
        "base_modules/workspace/models.py",
        "base_modules/workspace/permissions.py",
        "base_modules/workspace/management/commands/grant_workspace_member.py",
        "base_modules/key_manager/models.py",
        "base_modules/celery/views.py",
    }
    for migration in (repository_root / "base_modules").rglob("migrations/*.py"):
        if "links" not in migration.parts:
            expected.add(migration.relative_to(repository_root).as_posix())
    missing = expected - names
    forbidden = {
        name for name in names
        if name.startswith(("plugins/", "extensions/", "mixtum_instance/"))
        or "/__pycache__/" in name
        or name.endswith((".pyc", ".env", "db.sqlite3", ".DS_Store"))
        or name.startswith("base_modules/links/")
    }
    if missing or forbidden:
        raise SystemExit(f"Wheel non valido: mancanti={sorted(missing)}, vietati={sorted(forbidden)}")
    print(f"Wheel Platform verificato: {len(names)} file, tutte le migration presenti.")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Uso: python scripts/verify-platform-wheel.py /percorso/mixtum_platform_backend.whl")
    verify(Path(sys.argv[1]), Path(__file__).resolve().parents[1])
