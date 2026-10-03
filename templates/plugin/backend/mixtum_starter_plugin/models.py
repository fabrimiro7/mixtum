from django.conf import settings
from django.db import models

from base_modules.workspace.models import Workspace


class Item(models.Model):
    workspace = models.ForeignKey(Workspace, on_delete=models.CASCADE, related_name="starter_plugin_items")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    name = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)
