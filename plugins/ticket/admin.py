from django.contrib import admin

from .models import AssistanceManager, ClientCompany, CompanyMembership, OperatorGrant, Ticket


class SuperuserOnlyAdmin(admin.ModelAdmin):
    def has_module_permission(self, request):
        return request.user.is_superuser

    def has_view_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_add_permission(self, request):
        return request.user.is_superuser

    def has_change_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser


@admin.register(ClientCompany)
class ClientCompanyAdmin(SuperuserOnlyAdmin):
    list_display = ("name", "workspace")
    list_filter = ("workspace",)
    search_fields = ("name",)


@admin.register(CompanyMembership)
class CompanyMembershipAdmin(SuperuserOnlyAdmin):
    list_display = ("company", "user", "role")
    list_filter = ("role", "company__workspace")


@admin.register(OperatorGrant)
class OperatorGrantAdmin(SuperuserOnlyAdmin):
    list_display = ("company", "user")
    list_filter = ("company__workspace",)


@admin.register(AssistanceManager)
class AssistanceManagerAdmin(SuperuserOnlyAdmin):
    list_display = ("workspace", "user")
    list_filter = ("workspace",)


@admin.register(Ticket)
class TicketAdmin(SuperuserOnlyAdmin):
    list_display = ("title", "company", "workspace", "requester", "status", "assigned_to", "created_at")
    list_filter = ("workspace", "status")
    search_fields = ("title", "description")
    readonly_fields = ("created_at", "updated_at")

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("company", "workspace", "requester", "assigned_to")
