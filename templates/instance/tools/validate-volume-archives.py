"""Reject archive members that cannot safely be restored inside a Docker volume."""

import pathlib
import sys
import tarfile


root = pathlib.Path(sys.argv[1])
for volume in ("postgres_data", "keycloak_data", "media_data"):
    with tarfile.open(root / f"{volume}.tar.gz", "r:gz") as archive:
        for member in archive:
            path = pathlib.PurePosixPath(member.name)
            if (
                path.is_absolute()
                or ".." in path.parts
                or not (member.isfile() or member.isdir())
            ):
                raise ValueError("Unsafe archive member")
