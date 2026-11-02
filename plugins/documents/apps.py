from django.apps import AppConfig


class DocumentsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "plugins.documents"
    verbose_name = "Mixtum Documents"

    def ready(self):
        from . import registrations  # noqa: F401

