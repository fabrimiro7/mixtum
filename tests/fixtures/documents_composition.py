"""Test-only composition proving Documents as an independently selected product."""

CAPABILITIES = ("ai_labs",)
PLUGINS = (
    "plugins.plugin_example.manifest",
    "plugins.links.manifest",
    "plugins.ticket.manifest",
    "plugins.documents.manifest",
)
