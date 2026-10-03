"""Declarative contract; importing this module must not import Django models."""

PLUGIN = {
    "id": "plugin_example",
    "version": "0.1.0",
    "platform_api": "0.1",
    "django_app": "plugins.plugin_example",
    "url_prefix": "api/plugin-example/",
    "urlconf": "plugins.plugin_example.urls",
    "console_package": "@mixtum/plugin-example-console",
    "required_capabilities": (),
    "required_plugins": (),
}
