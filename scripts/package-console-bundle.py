#!/usr/bin/env python3
"""Build the versioned Console source bundle consumed by an instance build."""

import argparse
import io
import tarfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VERSION = "0.1.0"
FILES = (
    "console/package.json",
    "console/package-lock.json",
    "console/angular.json",
    "console/tsconfig.json",
    "console/tsconfig.app.json",
    "console/tsconfig.spec.json",
    "console/.postcssrc.json",
)
SOURCES = (
    "console/src",
    "packages/console-api",
    "plugins/plugin_example/console",
    "plugins/links/console",
    "plugins/ticket/console",
    "extensions/demo_support/console",
)


def add_file(archive, relative):
    source = ROOT / relative
    if not source.is_file() or source.is_symlink():
        raise ValueError(f"Missing or linked Console input: {relative}")
    data = source.read_bytes()
    info = tarfile.TarInfo(relative.as_posix())
    info.size = len(data)
    info.mode = 0o644
    info.mtime = 0
    archive.addfile(info, io.BytesIO(data))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("Output already exists; choose a new path")
    with tarfile.open(args.output, "w:gz") as archive:
        version = f"{VERSION}\n".encode()
        info = tarfile.TarInfo("BUNDLE_VERSION")
        info.size = len(version)
        info.mode = 0o644
        info.mtime = 0
        archive.addfile(info, io.BytesIO(version))
        for name in FILES:
            add_file(archive, Path(name))
        for directory in SOURCES:
            for source in sorted((ROOT / directory).rglob("*")):
                if source.is_symlink():
                    raise ValueError(f"Linked Console input: {source}")
                if source.is_file() and not any(part.startswith(".") for part in source.relative_to(ROOT / directory).parts):
                    add_file(archive, source.relative_to(ROOT))
    print(args.output)


if __name__ == "__main__":
    main()
