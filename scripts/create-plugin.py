#!/usr/bin/env python3
"""Create an ordinary Django/Angular Mixtum plugin in a new directory."""

import argparse
import os
from pathlib import Path
import re
import shutil
import sys
import tempfile


TEMPLATE = Path(__file__).resolve().parents[1] / "templates/plugin"
SLUG = re.compile(r"[a-z][a-z0-9]*(?:_[a-z0-9]+)*\Z")


def create(plugin_id: str, destination: Path) -> Path:
    if len(plugin_id) > 32 or not SLUG.fullmatch(plugin_id):
        raise ValueError("ID non valido: usa al massimo 32 caratteri a-z, 0-9 e underscore interni")
    if destination.exists() or destination.is_symlink():
        raise FileExistsError(f"La destinazione esiste già: {destination}")
    parent = destination.parent.resolve(strict=True)
    if not parent.is_dir():
        raise ValueError(f"La directory padre non è valida: {parent}")
    destination = parent / destination.name

    words = plugin_id.split("_")
    hyphen = "-".join(words)
    pascal = "".join(word.capitalize() for word in words)
    camel = pascal[0].lower() + pascal[1:]
    label = " ".join(word.capitalize() for word in words)
    substitutions = {
        "starter_plugin": plugin_id,
        "starter-plugin": hyphen,
        "StarterPlugin": pascal,
        "starterPlugin": camel,
        "Starter plugin": label,
    }

    staging = Path(tempfile.mkdtemp(prefix=f".{destination.name}.", dir=parent))
    try:
        shutil.copytree(TEMPLATE, staging, dirs_exist_ok=True)
        package = staging / "backend/mixtum_starter_plugin"
        package.rename(staging / f"backend/mixtum_{plugin_id}")
        for file in staging.rglob("*"):
            if file.is_file():
                content = file.read_text(encoding="utf-8")
                for old, new in substitutions.items():
                    content = content.replace(old, new)
                file.write_text(content, encoding="utf-8")
        if destination.exists() or destination.is_symlink():
            raise FileExistsError(f"La destinazione è stata creata durante la generazione: {destination}")
        os.rename(staging, destination)
    except BaseException:
        shutil.rmtree(staging)
        raise
    return destination


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plugin_id", help="ID del plugin, per esempio customer_portal")
    parser.add_argument("destination", type=Path, help="Nuova directory del plugin")
    args = parser.parse_args()
    try:
        created = create(args.plugin_id, args.destination)
    except (FileExistsError, OSError, ValueError) as exc:
        print(exc, file=sys.stderr)
        return 1
    print(f"Plugin creato in {created}")
    print("Leggi README.md; costruisci wheel e tarball, poi registrali esplicitamente nell’istanza.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
