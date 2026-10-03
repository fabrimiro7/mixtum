#!/usr/bin/env bash
set -euo pipefail

action=build
if [[ "${1:-}" == "--add-package" ]]; then
    [[ $# -eq 3 ]] || { printf 'Uso: %s --add-package /percorso/istanza /percorso/plugin.tgz\n' "$0" >&2; exit 2; }
    action=add-package
    instance_path="$2"
    package_path="$3"
elif [[ "${1:-}" == "--dev" ]]; then
    [[ $# -eq 3 ]] || { printf 'Uso: %s --dev /percorso/istanza /percorso/plugin/console\n' "$0" >&2; exit 2; }
    action=dev
    instance_path="$2"
    plugin_source="$3"
else
    [[ $# -eq 1 ]] || { printf 'Uso: %s /percorso/istanza\n' "$0" >&2; exit 2; }
    instance_path="$1"
fi
if [[ "$action" == dev ]]; then
    [[ -d "$plugin_source" && -f "$plugin_source/package.json" ]] || {
        printf 'Indica una directory sorgente Console con package.json.\n' >&2; exit 2;
    }
    plugin_source="$(cd "$plugin_source" && pwd -P)"
    dev_port="${CONSOLE_DEV_PORT:-4200}"
    [[ "$dev_port" =~ ^[0-9]+$ && "$dev_port" -ge 1 && "$dev_port" -le 65535 ]] || {
        printf 'CONSOLE_DEV_PORT deve essere una porta valida.\n' >&2; exit 2;
    }
fi
instance_root="$(cd "$instance_path" && pwd -P)"
bundle_path="${CONSOLE_BUNDLE:-}"
source_root="${MIXTUM_SOURCE:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)}"
if [[ "$action" == add-package ]]; then
    [[ -n "$bundle_path" ]] || { printf 'CONSOLE_BUNDLE è richiesto per aggiungere un pacchetto.\n' >&2; exit 2; }
    [[ "$package_path" == *.tgz && -f "$package_path" && ! -L "$package_path" ]] || {
        printf 'Indica un tarball npm .tgz regolare.\n' >&2; exit 2;
    }
fi
[[ -n "$bundle_path" || "$instance_root" != "$source_root" ]] || {
    printf 'La build richiede una istanza separata.\n' >&2; exit 2;
}
for file in \
    "$instance_root/mixtum_instance/composition.json" \
    "$instance_root/console/plugins.ts" \
    "$instance_root/console/mixtum-config.json"; do
    [[ -f "$file" ]] || { printf 'File istanza mancante: %s\n' "$file" >&2; exit 1; }
done
for executable in npm rsync python3; do
    command -v "$executable" >/dev/null 2>&1 || { printf 'Comando richiesto assente: %s\n' "$executable" >&2; exit 1; }
done

work_root="$(mktemp -d "${TMPDIR:-/tmp}/mixtum-console-build.XXXXXX")"
trap 'rm -rf "$work_root"' EXIT
if [[ -n "$bundle_path" ]]; then
    [[ -f "$bundle_path" ]] || { printf 'Bundle Console non trovato: %s\n' "$bundle_path" >&2; exit 1; }
    python3 - "$bundle_path" "$work_root" <<'PY'
import pathlib
import sys
import tarfile

destination = pathlib.Path(sys.argv[2])
allowed = ("console/", "packages/console-api/", "plugins/plugin_example/console/",
           "plugins/links/console/", "plugins/ticket/console/",
           "extensions/demo_support/console/")
seen = set()
with tarfile.open(sys.argv[1], "r:gz") as archive:
    members = archive.getmembers()
    if sum(member.size for member in members) > 100_000_000:
        raise SystemExit("Bundle Console troppo grande")
    for member in members:
        path = pathlib.PurePosixPath(member.name)
        if (not member.isfile() or member.name in seen or path.is_absolute()
                or ".." in path.parts or not (member.name == "BUNDLE_VERSION"
                or member.name.startswith(allowed))):
            raise SystemExit(f"Elemento non consentito nel bundle Console: {member.name}")
        seen.add(member.name)
    if "BUNDLE_VERSION" not in seen or archive.extractfile("BUNDLE_VERSION").read() != b"0.1.0\n":
        raise SystemExit("Versione bundle Console incompatibile")
    for member in members:
        target = destination / member.name
        target.parent.mkdir(parents=True, exist_ok=True)
        with archive.extractfile(member) as source, target.open("xb") as output:
            while chunk := source.read(1024 * 1024):
                output.write(chunk)
PY
else
    [[ -d "$source_root/console" ]] || { printf 'Checkout Mixtum non trovato: %s\n' "$source_root" >&2; exit 1; }
    rsync -a --exclude node_modules --exclude dist --exclude .angular \
        "$source_root/console/" "$work_root/console/"
    ln -s "$source_root/packages" "$work_root/packages"
    ln -s "$source_root/plugins" "$work_root/plugins"
    ln -s "$source_root/extensions" "$work_root/extensions"
fi
if [[ -e "$instance_root/console/package.json" || -e "$instance_root/console/package-lock.json" ]]; then
    for name in package.json package-lock.json; do
        file="$instance_root/console/$name"
        [[ -f "$file" && ! -L "$file" ]] || {
            printf 'Manifest Console dell’istanza incompleti o collegati: %s\n' "$name" >&2; exit 1;
        }
        cp "$file" "$work_root/console/$name"
    done
fi
if [[ -e "$instance_root/console/vendor" ]]; then
    [[ -d "$instance_root/console/vendor" && ! -L "$instance_root/console/vendor" ]] || {
        printf 'console/vendor deve essere una directory reale.\n' >&2; exit 1;
    }
    mkdir -p "$work_root/console/vendor"
    for file in "$instance_root/console/vendor/"*.tgz; do
        [[ -e "$file" ]] || continue
        [[ -f "$file" && ! -L "$file" ]] || { printf 'Tarball Console non regolare.\n' >&2; exit 1; }
        cp "$file" "$work_root/console/vendor/"
    done
fi
if [[ "$action" == add-package ]]; then
    package_name="$(basename "$package_path")"
    if [[ -e "$work_root/console/vendor/$package_name" ]]; then
        cmp -s "$package_path" "$work_root/console/vendor/$package_name" || {
            printf 'Esiste già un tarball diverso con lo stesso nome: %s\n' "$package_name" >&2; exit 1;
        }
    fi
    mkdir -p "$work_root/console/vendor"
    cp "$package_path" "$work_root/console/vendor/$package_name"
    (
        cd "$work_root/console"
        npm install --package-lock-only --save-exact --save-prod "file:vendor/$package_name" --cache "$work_root/npm-cache"
    )
    [[ ! -L "$instance_root/console/vendor" && ! -L "$instance_root/console/package.json" && ! -L "$instance_root/console/package-lock.json" ]] || {
        printf 'I percorsi Console dell’istanza non possono essere symlink.\n' >&2; exit 1;
    }
    mkdir -p "$instance_root/console/vendor"
    cp "$work_root/console/vendor/$package_name" "$instance_root/console/vendor/$package_name"
    cp "$work_root/console/package.json" "$instance_root/console/package.json"
    cp "$work_root/console/package-lock.json" "$instance_root/console/package-lock.json"
    printf 'Pacchetto Console registrato in %s; aggiorna console/plugins.ts per abilitarne la route.\n' "$instance_root"
    exit 0
fi
cp -R "$instance_root/mixtum_instance" "$work_root/mixtum_instance"
cp "$instance_root/console/plugins.ts" "$work_root/console/src/instance/plugins.ts"
cp "$instance_root/console/mixtum-config.json" "$work_root/console/src/assets/mixtum-config.json"

(
    cd "$work_root/console"
    npm ci --cache "$work_root/npm-cache"
    if [[ "$action" == dev ]]; then
        npm install --no-save "file:$plugin_source" --cache "$work_root/npm-cache"
        printf 'Console dev: http://127.0.0.1:%s/ (sorgente plugin: %s)\n' "$dev_port" "$plugin_source"
        npm run start -- --host 127.0.0.1 --port "$dev_port"
    else
        npm run build
    fi
)

if [[ "$action" == dev ]]; then
    exit 0
fi

output="$instance_root/artifacts/console/browser"
[[ ! -L "$instance_root/artifacts" && ! -L "$instance_root/artifacts/console" && ! -L "$output" ]] || {
    printf 'Il percorso artefatti non può essere un symlink.\n' >&2; exit 1;
}
mkdir -p "$output"
rsync -a --delete "$work_root/console/dist/adr-payment-hub/browser/" "$output/"
printf 'Console costruita in %s\n' "$output"
