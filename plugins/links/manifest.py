"""Instance-selected Links plugin contract; no model imports at settings time."""

PLUGIN = {
    "id": "links",
    "version": "0.1.0",
    "platform_api": "0.1",
    "django_app": "plugins.links",
    "url_prefix": "api/plugin-links/",
    "urlconf": "plugins.links.urls",
    "console_package": "@mixtum/plugin-links-console",
    "required_capabilities": (),
    "required_plugins": (),
}
