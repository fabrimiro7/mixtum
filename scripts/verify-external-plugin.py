#!/usr/bin/env python3
"""Exercise a new plugin ID from an isolated checkout and generated instance."""

import argparse
import os
from pathlib import Path
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import time
from urllib.request import urlopen


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/fixtures/external_probe"


def run(*command, cwd=None, env=None):
    result = subprocess.run(command, cwd=cwd, env=env, text=True, capture_output=True)
    if result.returncode:
        raise RuntimeError(
            f"Command failed ({result.returncode}): {' '.join(map(str, command))}\n"
            f"{result.stdout}\n{result.stderr}"
        )
    return result.stdout.strip()


def prepare(temp_root, generated):
    checkout = temp_root / "external-checkout"
    if generated:
        run(sys.executable, ROOT / "scripts/create-plugin.py", "inventory_portal", checkout)
        plugin_id = "inventory_portal"
        module = "mixtum_inventory_portal"
        chunk_name = "mixtum-plugin-inventory-portal-console-item-page-component"
    else:
        shutil.copytree(FIXTURE, checkout)
        plugin_id = "external_probe"
        module = "external_probe"
        chunk_name = "mixtum-plugin-external-probe-console-probe-page-component"
    instance = temp_root / "instance"
    run("bash", ROOT / "scripts/create-project.sh", instance)

    run("make", "plugin-register", f"PLUGIN_SOURCE={checkout}", cwd=instance)
    return checkout, instance, plugin_id, module, chunk_name


def verify_backend(checkout, instance, temp_root, python, platform_wheel, plugin_id, module, generated):
    wheelhouse = temp_root / "wheels"
    wheelhouse.mkdir()
    run(sys.executable, "-m", "pip", "wheel", "--no-deps", "--wheel-dir", wheelhouse,
        checkout / "backend")
    wheel = wheelhouse / f"mixtum_plugin_{plugin_id}_backend-0.1.0-py3-none-any.whl"
    if not wheel.is_file():
        raise RuntimeError("External plugin wheel missing")
    installed = temp_root / "installed"
    run(python, "-m", "pip", "install", "--no-deps", "--target", installed, platform_wheel, wheel)

    env = os.environ.copy()
    for line in (instance / ".env").read_text().splitlines():
        if line.startswith("SECRET_KEY="):
            env["SECRET_KEY"] = line.partition("=")[2]
    env.update(PYTHONPATH=str(installed), POSTGRES_HOST="", AUTH_MODE="django", USE_S3="0")
    run(python, "manage.py", "check", cwd=instance, env=env)
    if generated:
        run(python, "manage.py", "makemigrations", "--check", "--dry-run", cwd=instance, env=env)
    run(python, "manage.py", "test", f"{module}.tests", "--noinput", cwd=instance, env=env)
    origin = run(
        python, "-c", f"import {module}; print({module}.__file__)", cwd=instance, env=env,
    )
    if not Path(origin).resolve().is_relative_to(installed.resolve()):
        raise RuntimeError(f"Plugin was not loaded from installed wheel: {origin}")
    print("PASS: external backend wheel, Django check, workspace API tests")


def verify_backend_image(checkout, instance, temp_root, base_wheelhouse, plugin_id, module):
    wheelhouse = temp_root / "wheels"
    wheelhouse.mkdir()
    for source in base_wheelhouse.glob("*.whl"):
        if not source.is_file() or source.is_symlink():
            raise RuntimeError("Base wheelhouse contains a non-regular wheel")
        shutil.copy2(source, wheelhouse / source.name)
    run(sys.executable, "-m", "pip", "wheel", "--no-deps", "--wheel-dir", wheelhouse,
        checkout / "backend")
    expected_wheel = wheelhouse / f"mixtum_plugin_{plugin_id}_backend-0.1.0-py3-none-any.whl"
    if not expected_wheel.is_file():
        raise RuntimeError("External plugin wheel missing from image wheelhouse")
    run("make", "stage-wheels", f"WHEELHOUSE={wheelhouse}", cwd=instance)
    image = run("docker", "build", "--quiet", instance)
    if not image.startswith("sha256:"):
        raise RuntimeError("Docker did not return an image ID")
    environment = ["-e", "SECRET_KEY=ci-only-placeholder", "-e", "AUTH_MODE=django",
                   "-e", "POSTGRES_HOST=", "-e", "USE_S3=0"]
    run("docker", "run", "--rm", *environment, image, "python", "manage.py", "check")
    run("docker", "run", "--rm", *environment, image, "python", "manage.py", "test",
        f"{module}.tests", "--noinput")
    origin = run("docker", "run", "--rm", *environment, image, "python", "-c",
                 f"import {module}; print({module}.__file__)")
    if "/site-packages/" not in origin or "/app/" in origin:
        raise RuntimeError("External plugin was not loaded from the image wheel")
    print("PASS: external backend plugin installed from wheel in generated instance image")


def verify_frontend(checkout, instance, temp_root, chunk_name, generated):
    source_console = ROOT / "console"
    types = ROOT / "packages/console-api/dist/types/mixtum-console-api.d.ts"
    if not types.is_file():
        raise RuntimeError("Build @mixtum/console-api before this proof")
    if generated:
        vendor = checkout / "console/vendor"
        vendor.mkdir()
        api_tarball = run(
            "npm", "pack", ROOT / "packages/console-api/dist", "--pack-destination", vendor,
            "--cache", temp_root / "npm-cache", "--silent",
        )
        run("npm", "install", "--save-dev", "--save-exact", f"file:vendor/{api_tarball}",
            "--cache", temp_root / "npm-cache", cwd=checkout / "console")
        run("npm", "ci", "--cache", temp_root / "npm-cache", cwd=checkout / "console")
        packagr = checkout / "console/node_modules/.bin/ng-packagr"
    else:
        (checkout / "console/node_modules").symlink_to(source_console / "node_modules", target_is_directory=True)
        packagr = source_console / "node_modules/.bin/ng-packagr"
    run(
        packagr,
        "-p", checkout / "console/ng-package.json",
        "-c", checkout / "console/tsconfig.lib.json",
    )
    packed_name = run(
        "npm", "pack", checkout / "console/dist", "--pack-destination", temp_root,
        "--cache", temp_root / "npm-cache", "--silent",
    )
    tarball = temp_root / packed_name
    bundle = temp_root / "mixtum-console-0.1.0.tar.gz"
    run(sys.executable, ROOT / "scripts/package-console-bundle.py", bundle)
    run(
        "make", "-C", instance, "console-add-package", f"CONSOLE_BUNDLE={bundle}", f"PACKAGE={tarball}",
    )
    build_output = run("make", "-C", instance, "console-build", f"CONSOLE_BUNDLE={bundle}")
    browser = instance / "artifacts/console/browser"
    if (chunk_name not in build_output
            or not any(browser.glob("chunk-*.js"))):
        raise RuntimeError("External plugin lazy page missing from Console build")
    print("PASS: external Angular tarball, instance lockfile, Console lazy page")


def verify_reload(checkout, instance, temp_root):
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
    log_path = temp_root / "ng-serve.log"
    with log_path.open("w+") as log:
        server = subprocess.Popen(
            ["make", "-C", instance, "console-dev", f"PLUGIN_SOURCE={checkout / 'console'}",
             f"CONSOLE_DEV_PORT={port}"],
            stdout=log, stderr=subprocess.STDOUT, text=True, start_new_session=True,
        )
        try:
            deadline = time.monotonic() + 75
            while time.monotonic() < deadline:
                if server.poll() is not None:
                    raise RuntimeError(f"Angular dev server exited:\n{log_path.read_text()}")
                try:
                    with urlopen(f"http://127.0.0.1:{port}/", timeout=2) as response:
                        if response.status == 200:
                            break
                except OSError:
                    time.sleep(1)
            else:
                raise RuntimeError(f"Angular dev server did not start:\n{log_path.read_text()}")

            component = checkout / "console/src/item-page.component.ts"
            source = component.read_text()
            marker = "<h1 id=\"inventory-portal-title\">Inventory Portal</h1>"
            if source.count(marker) != 1:
                raise RuntimeError("Generated page marker changed")
            log_size = log_path.stat().st_size
            component.write_text(source.replace(marker, marker + "<p>Reload probe</p>"))
            deadline = time.monotonic() + 45
            while time.monotonic() < deadline:
                output = log_path.read_text()[log_size:].lower()
                if ("component update sent to client(s)" in output
                        or "page reload sent to client(s)" in output) and "error" not in output:
                    print("PASS: external generated source change triggers Angular dev update without npm install")
                    return
                if server.poll() is not None:
                    raise RuntimeError(f"Angular dev server exited after edit:\n{log_path.read_text()}")
                time.sleep(1)
            raise RuntimeError(f"Angular did not reload after external source edit:\n{log_path.read_text()}")
        finally:
            try:
                os.killpg(server.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
            try:
                server.wait(timeout=10)
            except subprocess.TimeoutExpired:
                os.killpg(server.pid, signal.SIGKILL)
                server.wait(timeout=10)


def verify_backend_reload(checkout, instance, temp_root, python, platform_wheel):
    source_venv = python.parent.parent
    if not (source_venv / "pyvenv.cfg").is_file():
        raise RuntimeError("--python must point to a prepared virtualenv")
    shutil.copytree(source_venv, instance / ".venv", symlinks=True)
    local_python = instance / ".venv/bin/python"
    run(local_python, "-m", "pip", "install", "--no-deps", "--force-reinstall", platform_wheel)

    env_file = instance / ".env"
    lines = env_file.read_text().splitlines()
    lines = ["AUTH_MODE=django" if line.startswith("AUTH_MODE=") else line for line in lines]
    lines = ["POSTGRES_HOST=" if line.startswith("POSTGRES_HOST=") else line for line in lines]
    env_file.write_text("\n".join(lines) + "\n")
    env = os.environ.copy()
    for line in lines:
        if line.startswith(("SECRET_KEY=", "AUTH_MODE=", "POSTGRES_HOST=", "USE_S3=")):
            key, _, value = line.partition("=")
            env[key] = value
    env["PIP_CACHE_DIR"] = str(temp_root / "pip-cache")
    run("make", "-C", instance, "plugin-backend-editable", f"PLUGIN_SOURCE={checkout}", env=env)
    origin = run(local_python, "-c", "import mixtum_inventory_portal; print(mixtum_inventory_portal.__file__)",
                 cwd=instance, env=env)
    if not Path(origin).resolve().is_relative_to((checkout / "backend").resolve()):
        raise RuntimeError(f"Editable plugin is not loaded from external source: {origin}")
    run(local_python, "manage.py", "migrate", "--noinput", cwd=instance, env=env)

    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
    log_path = temp_root / "runserver.log"
    with log_path.open("w+") as log:
        server = subprocess.Popen(
            ["make", "-C", instance, "backend-dev", f"BACKEND_DEV_PORT={port}"],
            env=env, stdout=log, stderr=subprocess.STDOUT, text=True, start_new_session=True,
        )
        try:
            deadline = time.monotonic() + 45
            while time.monotonic() < deadline:
                if server.poll() is not None:
                    raise RuntimeError(f"Django dev server exited:\n{log_path.read_text()}")
                try:
                    with urlopen(f"http://127.0.0.1:{port}/health/live/", timeout=2) as response:
                        if response.status == 200:
                            break
                except OSError:
                    time.sleep(1)
            else:
                raise RuntimeError(f"Django dev server did not start:\n{log_path.read_text()}")

            views = checkout / "backend/mixtum_inventory_portal/views.py"
            log_size = log_path.stat().st_size
            views.write_text(views.read_text() + "\n# Reload probe in temporary checkout.\n")
            deadline = time.monotonic() + 30
            while time.monotonic() < deadline:
                output = log_path.read_text()[log_size:].lower()
                if "changed, reloading" in output:
                    try:
                        with urlopen(f"http://127.0.0.1:{port}/health/live/", timeout=2) as response:
                            if response.status == 200:
                                print("PASS: external editable Django source reloads without reinstall")
                                return
                    except OSError:
                        pass  # The listener can briefly close while Django restarts.
                if server.poll() is not None:
                    raise RuntimeError(f"Django dev server exited after edit:\n{log_path.read_text()}")
                time.sleep(1)
            raise RuntimeError(f"Django did not reload after external source edit:\n{log_path.read_text()}")
        finally:
            try:
                os.killpg(server.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
            try:
                server.wait(timeout=10)
            except subprocess.TimeoutExpired:
                os.killpg(server.pid, signal.SIGKILL)
                server.wait(timeout=10)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backend", action="store_true")
    parser.add_argument("--backend-image", action="store_true", help="Verify external wheel in generated Docker image")
    parser.add_argument("--frontend", action="store_true")
    parser.add_argument("--reload", action="store_true", help="Verify Angular reload of generated source")
    parser.add_argument("--backend-reload", action="store_true", help="Verify Django reload of generated source")
    parser.add_argument("--python", type=Path, help="Python from an instance with Platform wheel installed")
    parser.add_argument("--platform-wheel", type=Path, help="Platform wheel under test")
    parser.add_argument("--wheelhouse", type=Path, help="Base Platform and plugin wheels for image proof")
    parser.add_argument("--generated", action="store_true", help="Verify the generated inventory_portal plugin")
    args = parser.parse_args()
    if sum((args.backend, args.backend_image, args.frontend, args.reload, args.backend_reload)) != 1:
        parser.error("Choose exactly one verification mode")
    if (args.backend or args.backend_reload) and (not args.python or not args.platform_wheel):
        parser.error("backend verification requires --python and --platform-wheel")
    if (args.reload or args.backend_reload) and not args.generated:
        parser.error("reload verification requires --generated")
    if args.backend_image and (not args.wheelhouse or not args.wheelhouse.is_dir()):
        parser.error("backend image verification requires --wheelhouse")

    with tempfile.TemporaryDirectory(prefix="mixtum-external-plugin-") as directory:
        temp_root = Path(directory)
        checkout, instance, plugin_id, module, chunk_name = prepare(temp_root, args.generated)
        if args.backend:
            # Resolving bin/python follows the virtualenv symlink to the base
            # interpreter and drops the environment's installed dependencies.
            verify_backend(checkout, instance, temp_root, args.python.absolute(), args.platform_wheel.resolve(),
                           plugin_id, module, args.generated)
        elif args.backend_image:
            verify_backend_image(checkout, instance, temp_root, args.wheelhouse.resolve(), plugin_id, module)
        elif args.frontend:
            verify_frontend(checkout, instance, temp_root, chunk_name, args.generated)
        elif args.reload:
            verify_reload(checkout, instance, temp_root)
        else:
            # Preserve the venv path: resolving bin/python follows its symlink to the base interpreter.
            verify_backend_reload(checkout, instance, temp_root, args.python.absolute(), args.platform_wheel.resolve())


if __name__ == "__main__":
    main()
