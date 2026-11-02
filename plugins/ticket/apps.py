from django.apps import AppConfig


class TicketConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "plugins.ticket"
    verbose_name = "Mixtum Ticket"

    def ready(self):
        from . import ai_tools  # noqa: F401
