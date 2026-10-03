from django.contrib import admin
from django.contrib.auth.hashers import identify_hasher
from .models import ExternalIdentity, User

@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ("id", "email", "username", "permission", "is_active", "is_staff", "is_superuser")
    search_fields = ("email", "username", "first_name", "last_name")
    list_filter = ("is_active", "is_staff", "is_superuser", "permission", "user_type")

    def save_model(self, request, obj, form, change):
        # Se il campo password è stato toccato, controlla se è in chiaro
        if change and "password" in form.changed_data:
            try:
                # Se non esplode, è già un hash valido (pbkdf2/argon2/bcrypt...)
                identify_hasher(obj.password)
            except Exception:
                # Non è un hash: è una password in chiaro -> cifra
                obj.set_password(obj.password)
        super().save_model(request, obj, form, change)


@admin.register(ExternalIdentity)
class ExternalIdentityAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "issuer", "subject", "created_at")
    search_fields = ("issuer", "subject", "user__email", "user__username")
    autocomplete_fields = ("user",)
    readonly_fields = ("created_at",)

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
