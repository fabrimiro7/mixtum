"""Instance-specific composition using the same stable contract as a plugin."""

PLUGIN = {
    "id": "demo_support",
    "version": "0.1.0",
    "platform_api": "0.1",
    "django_app": "extensions.demo_support",
    "url_prefix": "api/demo-support/",
    "urlconf": "extensions.demo_support.urls",
    "console_package": "@mixtum/extension-demo-support-console",
    "required_capabilities": (),
    "required_plugins": ("ticket",),
}
