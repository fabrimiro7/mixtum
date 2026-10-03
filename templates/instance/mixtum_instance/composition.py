"""Explicit composition owned by this instance, not by the Mixtum checkout."""

import json
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured


AVAILABLE_PLUGINS = {
    "plugin_example": "plugins.plugin_example.manifest",
    "links": "plugins.links.manifest",
    "ticket": "plugins.ticket.manifest",
}
AVAILABLE_EXTENSIONS = {
    "demo_support": "extensions.demo_support.manifest",
}

configuration = json.loads(Path(__file__).with_name("composition.json").read_text())
if not isinstance(configuration, dict):
    raise ImproperlyConfigured("Instance composition must be an object")


def selected(key, available):
    names = configuration.get(key, [])
    if not isinstance(names, list) or not all(isinstance(name, str) for name in names):
        raise ImproperlyConfigured(f"{key} must be a list of names")
    if len(names) != len(set(names)) or set(names) - available.keys():
        raise ImproperlyConfigured(f"Unknown or duplicate {key} in instance composition")
    return tuple(available[name] for name in names)


CAPABILITIES = configuration.get("capabilities", [])
if not isinstance(CAPABILITIES, list) or not all(isinstance(name, str) for name in CAPABILITIES):
    raise ImproperlyConfigured("capabilities must be a list of names")
CAPABILITIES = tuple(CAPABILITIES)
PLUGINS = selected("plugins", AVAILABLE_PLUGINS) + selected("extensions", AVAILABLE_EXTENSIONS)
