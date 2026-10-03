"""Instance-selected Ticket plugin contract; no model imports at settings time."""

PLUGIN = {
    "id": "ticket",
    "version": "0.1.0",
    "platform_api": "0.1",
    "django_app": "plugins.ticket",
    "url_prefix": "api/plugin-ticket/",
    "urlconf": "plugins.ticket.urls",
    "console_package": "@mixtum/plugin-ticket-console",
    "required_capabilities": (),
    "required_plugins": (),
}
