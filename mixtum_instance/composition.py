"""Composition root for the repository's default development instance."""

import json
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured


_available_manifests = {
    "plugin_example": "plugins.plugin_example.manifest",
    "links": "plugins.links.manifest",
    "ticket": "plugins.ticket.manifest",
}
_available_extensions = {
    "demo_support": "extensions.demo_support.manifest",
}
_configuration = json.loads(Path(__file__).with_name("composition.json").read_text())
if not isinstance(_configuration, dict):
    raise ImproperlyConfigured("Instance composition must be a JSON object")
_enabled = _configuration.get("plugins")
if not isinstance(_enabled, list) or not all(isinstance(item, str) for item in _enabled):
    raise ImproperlyConfigured("Invalid plugin selection in instance composition")
if len(_enabled) != len(set(_enabled)):
    raise ImproperlyConfigured("Duplicate or invalid plugin selection in instance composition")
if unknown := set(_enabled) - _available_manifests.keys():
    raise ImproperlyConfigured(f"Unknown instance plugins: {sorted(unknown)}")
_extensions = _configuration.get("extensions", [])
if not isinstance(_extensions, list) or not all(isinstance(item, str) for item in _extensions):
    raise ImproperlyConfigured("Invalid extension selection in instance composition")
if len(_extensions) != len(set(_extensions)):
    raise ImproperlyConfigured("Duplicate extension selection in instance composition")
if unknown := set(_extensions) - _available_extensions.keys():
    raise ImproperlyConfigured(f"Unknown instance extensions: {sorted(unknown)}")

CAPABILITIES = _configuration.get("capabilities")
if not isinstance(CAPABILITIES, list) or not all(isinstance(item, str) for item in CAPABILITIES):
    raise ImproperlyConfigured("Invalid capabilities in instance composition")
CAPABILITIES = tuple(CAPABILITIES)
PLUGINS = tuple(_available_manifests[plugin_id] for plugin_id in _enabled) + tuple(
    _available_extensions[extension_id] for extension_id in _extensions
)
