"""Validate trusted instance composition before Django loads its applications."""

from dataclasses import dataclass
from importlib import import_module
from importlib.util import find_spec
import re

from django.core.exceptions import ImproperlyConfigured


PLATFORM_API_VERSION = "0.1"
_RESERVED_URL_PREFIXES = {
    "api/workspace/", "api/branding/", "api/v1/", "api/attachments/",
    "api/links/", "api/slack/", "api/n8n/", "api/whatsapp/",
}


@dataclass(frozen=True)
class PluginDefinition:
    id: str
    version: str
    django_app: str
    url_prefix: str
    urlconf: str
    console_package: str | None
    required_capabilities: tuple[str, ...]
    required_plugins: tuple[str, ...]


def _string(value, field, manifest):
    if not isinstance(value, str) or not value:
        raise ImproperlyConfigured(f"{manifest}: {field} must be a non-empty string")
    return value


def _names(value, field, manifest):
    if not isinstance(value, (list, tuple)) or not all(
        isinstance(name, str) and re.fullmatch(r"[a-z][a-z0-9_-]*", name) for name in value
    ):
        raise ImproperlyConfigured(f"{manifest}: {field} must be a list of names")
    if len(value) != len(set(value)):
        raise ImproperlyConfigured(f"{manifest}: duplicate {field}")
    return tuple(value)


def _installed_module(value, field, manifest):
    module = _string(value, field, manifest)
    if not re.fullmatch(r"[a-zA-Z_]\w*(\.[a-zA-Z_]\w*)*", module):
        raise ImproperlyConfigured(f"{manifest}: invalid {field} module path")
    try:
        available = find_spec(module) is not None
    except (ImportError, ValueError):
        available = False
    if not available:
        raise ImproperlyConfigured(f"{manifest}: {field} module {module} is not installed")
    return module


def load_plugins(composition_module):
    """Load only explicitly selected manifests; disabled plugins are never imported."""
    try:
        composition = import_module(composition_module)
    except ImportError as exc:
        raise ImproperlyConfigured(f"Cannot import instance composition {composition_module}") from exc

    manifests = getattr(composition, "PLUGINS", ())
    if not isinstance(manifests, (list, tuple)) or not all(isinstance(item, str) for item in manifests):
        raise ImproperlyConfigured(f"{composition_module}: PLUGINS must be a list of module paths")
    capabilities = _names(getattr(composition, "CAPABILITIES", ()), "CAPABILITIES", composition_module)
    result = []
    ids, apps, prefixes = set(), set(), set()
    for manifest_path in manifests:
        try:
            raw = getattr(import_module(manifest_path), "PLUGIN")
        except (ImportError, AttributeError) as exc:
            raise ImproperlyConfigured(f"Cannot load plugin manifest {manifest_path}") from exc
        if not isinstance(raw, dict):
            raise ImproperlyConfigured(f"{manifest_path}: PLUGIN must be a dictionary")

        plugin_id = _string(raw.get("id"), "id", manifest_path)
        if not re.fullmatch(r"[a-z][a-z0-9_-]*", plugin_id):
            raise ImproperlyConfigured(f"{manifest_path}: invalid plugin id")
        version = _string(raw.get("version"), "version", manifest_path)
        if _string(raw.get("platform_api"), "platform_api", manifest_path) != PLATFORM_API_VERSION:
            raise ImproperlyConfigured(f"{manifest_path}: incompatible platform API")
        django_app = _installed_module(raw.get("django_app"), "django_app", manifest_path)
        url_prefix = _string(raw.get("url_prefix"), "url_prefix", manifest_path)
        if not re.fullmatch(r"api/[a-z][a-z0-9-]*/", url_prefix) or url_prefix in _RESERVED_URL_PREFIXES:
            raise ImproperlyConfigured(f"{manifest_path}: invalid or reserved URL prefix")
        urlconf = _installed_module(raw.get("urlconf"), "urlconf", manifest_path)
        console_package = raw.get("console_package")
        if console_package is not None:
            console_package = _string(console_package, "console_package", manifest_path)
        required_capabilities = _names(raw.get("required_capabilities", ()), "required_capabilities", manifest_path)
        required_plugins = _names(raw.get("required_plugins", ()), "required_plugins", manifest_path)
        if plugin_id in ids or django_app in apps or url_prefix in prefixes:
            raise ImproperlyConfigured(f"{manifest_path}: duplicate plugin id, Django app or URL prefix")
        ids.add(plugin_id)
        apps.add(django_app)
        prefixes.add(url_prefix)
        result.append(PluginDefinition(
            plugin_id, version, django_app, url_prefix, urlconf, console_package,
            required_capabilities, required_plugins,
        ))

    for plugin in result:
        missing_capabilities = set(plugin.required_capabilities) - set(capabilities)
        missing_plugins = set(plugin.required_plugins) - ids
        if missing_capabilities or missing_plugins:
            raise ImproperlyConfigured(
                f"{plugin.id}: missing capabilities {sorted(missing_capabilities)} "
                f"or plugins {sorted(missing_plugins)}"
            )
    return tuple(result)
