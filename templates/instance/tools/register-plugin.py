#!/usr/bin/env python3
"""Register an ordinary backend/Console plugin in this instance's source files."""

import argparse
import ast
import json
import os
from pathlib import Path
import re
import stat
import tempfile
import tomllib


SLUG = re.compile(r"[a-z][a-z0-9]*(?:_[a-z0-9]+)*\Z")
MODULE = re.compile(r"[a-z_][a-z0-9_]*\Z")


def regular_file(path: Path) -> str:
    if path.is_symlink() or path.parent.is_symlink() or not path.is_file():
        raise ValueError(f"File regolare richiesto: {path}")
    return path.read_text(encoding="utf-8")


def plugin_metadata(plugin: Path) -> tuple[str, str, str, str, str, str]:
    if plugin.is_symlink() or not plugin.is_dir():
        raise ValueError("Il checkout plugin deve essere una directory reale")
    if any((plugin / name).is_symlink() for name in ("backend", "console")):
        raise ValueError("Le directory backend e Console non possono essere symlink")
    manifests = list((plugin / "backend").glob("*/manifest.py"))
    if len(manifests) != 1 or manifests[0].parent.is_symlink():
        raise ValueError("Un solo manifest backend regolare è richiesto")
    manifest_file = manifests[0]
    tree = ast.parse(regular_file(manifest_file))
    assignments = [node.value for node in tree.body if isinstance(node, ast.Assign)
                   and any(isinstance(target, ast.Name) and target.id == "PLUGIN" for target in node.targets)]
    if len(assignments) != 1:
        raise ValueError("Il manifest deve dichiarare un solo PLUGIN statico")
    manifest = ast.literal_eval(assignments[0])
    if not isinstance(manifest, dict):
        raise ValueError("PLUGIN deve essere un dizionario")
    plugin_id = manifest.get("id")
    module = manifest.get("django_app")
    if not isinstance(plugin_id, str) or not SLUG.fullmatch(plugin_id):
        raise ValueError("ID plugin non valido")
    if not isinstance(module, str) or not MODULE.fullmatch(module) or manifest_file.parent.name != module:
        raise ValueError("Modulo Django del plugin non coerente")
    if manifest.get("platform_api") != "0.1":
        raise ValueError("Versione Platform API non compatibile con questa istanza")
    backend = tomllib.loads(regular_file(plugin / "backend/pyproject.toml")).get("project", {})
    frontend = json.loads(regular_file(plugin / "console/package.json"))
    version = manifest.get("version")
    if (not isinstance(version, str) or not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", version)
            or backend.get("version") != version
            or frontend.get("version") != version):
        raise ValueError("Versioni backend, manifest e Console non coerenti")
    distribution = backend.get("name")
    package = frontend.get("name")
    if (distribution != f"mixtum-plugin-{plugin_id.replace('_', '-')}-backend"
            or package != manifest.get("console_package")
            or not isinstance(package, str)
            or not re.fullmatch(r"(?:@[a-z0-9-]+/)?[a-z][a-z0-9-]*", package)):
        raise ValueError("Nomi dei pacchetti non coerenti con il manifest")
    index = regular_file(plugin / "console/src/index.ts")
    match = re.search(
        rf"export const ([A-Za-z_][A-Za-z0-9_]*): ConsolePluginContribution\s*=\s*\{{\s*id:\s*['\"]{re.escape(plugin_id)}['\"]",
        index,
    )
    if match is None:
        raise ValueError("Contributo Console con ID corrispondente non trovato")
    return plugin_id, f"{module}.manifest", distribution, package, match.group(1), version


def register(instance: Path, plugin: Path) -> None:
    if instance.is_symlink() or not instance.is_dir() or not (instance / "Makefile").is_file():
        raise ValueError("Indica una directory istanza Mixtum reale")
    plugin_id, manifest, distribution, package, contribution, version = plugin_metadata(plugin)
    paths = {
        "requirements": instance / "requirements.txt",
        "backend": instance / "mixtum_instance/composition.py",
        "composition": instance / "mixtum_instance/composition.json",
        "console": instance / "console/plugins.ts",
    }
    original = {key: regular_file(path) for key, path in paths.items()}
    configuration = json.loads(original["composition"])
    if not isinstance(configuration, dict) or not isinstance(configuration.get("plugins"), list):
        raise ValueError("Composizione JSON non riconosciuta")
    if plugin_id in configuration["plugins"]:
        raise ValueError("Plugin già abilitato nell'istanza")
    tree = ast.parse(original["backend"])
    mapping = [node.value for node in tree.body if isinstance(node, ast.Assign)
               and any(isinstance(target, ast.Name) and target.id == "AVAILABLE_PLUGINS" for target in node.targets)]
    if len(mapping) != 1 or not isinstance(mapping[0], ast.Dict):
        raise ValueError("Mappa plugin backend non riconosciuta")
    available = ast.literal_eval(mapping[0])
    if plugin_id in available or manifest in available.values():
        raise ValueError("Plugin già registrato nel backend")
    if package in original["console"] or contribution in original["console"]:
        raise ValueError("Contributo Console già registrato")
    if any(line.split("==", 1)[0].strip() == distribution for line in original["requirements"].splitlines()):
        raise ValueError("Requisito backend già registrato")

    backend_marker = "AVAILABLE_PLUGINS = {\n"
    console_import = "import { ConsolePluginContribution } from '@mixtum/console-api';\n"
    console_marker = "const available: readonly ConsolePluginContribution[] = [\n"
    for source, marker in ((original["backend"], backend_marker),
                           (original["console"], console_import),
                           (original["console"], console_marker)):
        if source.count(marker) != 1:
            raise ValueError("Formato della composizione modificato: registra il plugin manualmente")
    configuration["plugins"].append(plugin_id)
    updated = {
        "requirements": original["requirements"].rstrip("\n") + f"\n{distribution}=={version}\n",
    }
    updated["backend"] = original["backend"].replace(
        backend_marker, backend_marker + f'    "{plugin_id}": "{manifest}",\n', 1,
    )
    updated["composition"] = json.dumps(configuration, indent=2, ensure_ascii=False) + "\n"
    updated["console"] = original["console"].replace(
        console_import, console_import + f"import {{ {contribution} }} from '{package}';\n", 1,
    ).replace(console_marker, console_marker + f"  {contribution},\n", 1)

    staged = []
    backups = []
    replaced = []
    retain_backups = False
    try:
        for key, path in paths.items():
            descriptor, name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
            staged.append(Path(name))
            with os.fdopen(descriptor, "w", encoding="utf-8") as output:
                output.write(updated[key])
            os.chmod(name, stat.S_IMODE(path.stat().st_mode))
            descriptor, backup = tempfile.mkstemp(prefix=f".{path.name}.backup.", dir=path.parent)
            backups.append(Path(backup))
            with os.fdopen(descriptor, "w", encoding="utf-8") as output:
                output.write(original[key])
            os.chmod(backup, stat.S_IMODE(path.stat().st_mode))
        if any(regular_file(path) != original[key] for key, path in paths.items()):
            raise ValueError("Un file dell'istanza è cambiato durante la registrazione")
        try:
            for path, temporary in zip(paths.values(), staged):
                os.replace(temporary, path)
                replaced.append(path)
        except OSError:
            try:
                for path, backup in zip(paths.values(), backups):
                    if path in replaced:
                        os.replace(backup, path)
            except OSError as recovery_error:
                retain_backups = True
                raise RuntimeError(f"Ripristino dei file incompleto; controlla le copie {backups}") from recovery_error
            raise
    finally:
        for temporary in staged + ([] if retain_backups else backups):
            temporary.unlink(missing_ok=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plugin", type=Path, help="Checkout esterno del plugin")
    args = parser.parse_args()
    try:
        register(Path(__file__).resolve().parents[1], args.plugin)
    except (OSError, ValueError, SyntaxError, KeyError, TypeError, RuntimeError) as error:
        parser.exit(1, f"Registrazione non eseguita: {error}\n")
    print("Plugin registrato nei file dell'istanza. Costruisci/installane wheel e tarball, poi verifica l'istanza.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
