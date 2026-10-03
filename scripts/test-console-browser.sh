#!/usr/bin/env bash
set -euo pipefail

source_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
console_root="$source_root/console"
work_root="$(mktemp -d "${TMPDIR:-/tmp}/mixtum-console-test.XXXXXX")"
trap 'rm -rf "$work_root"' EXIT

(
    cd "$console_root"
    npm run build:plugin-packages
)

rsync -a --exclude node_modules --exclude dist --exclude .angular \
    "$console_root/" "$work_root/console/"
ln -s "$source_root/packages" "$work_root/packages"
ln -s "$source_root/plugins" "$work_root/plugins"
ln -s "$source_root/extensions" "$work_root/extensions"
ln -s "$source_root/mixtum_instance" "$work_root/mixtum_instance"

(
    cd "$work_root/console"
    npm pkg set \
        'dependencies.@mixtum/console-api=file:../packages/console-api/dist' \
        'dependencies.@mixtum/plugin-example-console=file:../plugins/plugin_example/console/dist' \
        'dependencies.@mixtum/plugin-links-console=file:../plugins/links/console/dist' \
        'dependencies.@mixtum/plugin-ticket-console=file:../plugins/ticket/console/dist' \
        'dependencies.@mixtum/extension-demo-support-console=file:../extensions/demo_support/console/dist'
    npm install --package-lock-only --cache "$work_root/npm-cache"
    npm ci --cache "$work_root/npm-cache"
    ./node_modules/.bin/ng test --watch=false
)
