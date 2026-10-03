from django.contrib import admin
from .models import Link


@admin.register(Link)
class LinkAdmin(admin.ModelAdmin):
    # Unassigned legacy rows need review; only platform superusers may inspect them.
    list_display = ("title", "workspace", "label", "url", "short_target", "created_at")
    list_filter = ("workspace", "label", "created_at")
    search_fields = ("title", "description", "url")

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("workspace", "content_type")

    def has_module_permission(self, request):
        return request.user.is_superuser

    def has_view_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
