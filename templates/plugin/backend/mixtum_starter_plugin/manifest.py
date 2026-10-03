"""Importable before Django loads models."""

PLUGIN = {
    "id": "starter_plugin",
    "version": "0.1.0",
    "platform_api": "0.1",
    "django_app": "mixtum_starter_plugin",
    "url_prefix": "api/starter-plugin/",
    "urlconf": "mixtum_starter_plugin.urls",
    "console_package": "mixtum-plugin-starter-plugin-console",
    "required_capabilities": (),
    "required_plugins": (),
}
