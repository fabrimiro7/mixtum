import re

from django.shortcuts import get_object_or_404
from rest_framework import permissions
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework.views import APIView

from base_modules.workspace.models import Workspace
from base_modules.workspace.models import AdminAuditEvent
from base_modules.workspace.services import can_manage_workspace, record_admin_event
from .constants import DEFAULT_COLORS
from .models import BrandingSettings
from .serializers import BrandingSettingsSerializer


class IsSuperAdmin(permissions.BasePermission):
    def has_permission(self, request, view):
        user = getattr(request, "user", None)
        if not user or not user.is_authenticated:
            return False
        return getattr(user, "is_superuser", False)


def _file_url(request, file_field):
    if not file_field:
        return None
    try:
        url = file_field.url
    except ValueError:
        return None
    return request.build_absolute_uri(url) if request else url


def _visible_workspace(request, workspace_id):
    user = request.user
    if not user.is_authenticated:
        raise PermissionDenied("Autenticazione richiesta")
    queryset = Workspace.objects.all()
    if not user.is_superuser:
        queryset = queryset.filter(workspaceuser__user=user)
    return get_object_or_404(queryset, pk=workspace_id)


def _console_theme(colors):
    # Legacy color settings may contain arbitrary strings; expose only a CSS-safe token.
    primary = colors.get("--ed-blue")
    if not isinstance(primary, str) or not re.fullmatch(r"#[0-9a-fA-F]{6}", primary):
        primary = DEFAULT_COLORS["--ed-blue"]
    channels = [int(primary[index:index + 2], 16) / 255 for index in (1, 3, 5)]
    linear = [channel / 12.92 if channel <= 0.04045 else ((channel + 0.055) / 1.055) ** 2.4
              for channel in channels]
    luminance = 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]
    return {"primary": primary, "on_primary": "#000000" if luminance > 0.179 else "#FFFFFF"}


class GlobalBrandingView(APIView):
    def get_permissions(self):
        if self.request.method in permissions.SAFE_METHODS:
            return [permissions.AllowAny()]
        return [IsSuperAdmin()]

    def get(self, request):
        instance = BrandingSettings.objects.filter(workspace__isnull=True).order_by("id").first()
        if not instance:
            return Response(
                {
                    "workspace": None,
                    "colors": {},
                    "logo_full": None,
                    "logo_compact": None,
                    "favicon": None,
                }
            )
        serializer = BrandingSettingsSerializer(instance, context={"request": request})
        return Response(serializer.data)

    def patch(self, request):
        instance = BrandingSettings.objects.filter(workspace__isnull=True).order_by("id").first()
        if not instance:
            instance = BrandingSettings.objects.create()
        serializer = BrandingSettingsSerializer(
            instance, data=request.data, partial=True, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        record_admin_event(
            actor=request.user,
            action="branding.global.update",
            outcome=AdminAuditEvent.SUCCESS,
        )
        return Response(serializer.data)


class WorkspaceBrandingView(APIView):
    def get_permissions(self):
        if self.request.method in permissions.SAFE_METHODS:
            return [permissions.IsAuthenticated()]
        return [permissions.IsAuthenticated()]

    def get(self, request, workspace_id: int):
        workspace = _visible_workspace(request, workspace_id)
        instance = BrandingSettings.objects.filter(workspace=workspace).first()
        if not instance:
            return Response(
                {
                    "workspace": workspace.id,
                    "colors": {},
                    "logo_full": None,
                    "logo_compact": None,
                    "favicon": None,
                }
            )
        serializer = BrandingSettingsSerializer(instance, context={"request": request})
        return Response(serializer.data)

    def patch(self, request, workspace_id: int):
        workspace = _visible_workspace(request, workspace_id)
        if not can_manage_workspace(user=request.user, workspace_id=workspace.pk):
            raise PermissionDenied("Solo un gestore del workspace può modificarne il branding.")
        instance, _created = BrandingSettings.objects.get_or_create(workspace=workspace)
        serializer = BrandingSettingsSerializer(
            instance, data=request.data, partial=True, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        record_admin_event(
            actor=request.user,
            action="branding.workspace.update",
            outcome=AdminAuditEvent.SUCCESS,
            workspace=workspace,
        )
        return Response(serializer.data)


class EffectiveBrandingView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        workspace_id_raw = request.query_params.get("workspace_id")
        try:
            workspace_id = int(workspace_id_raw) if workspace_id_raw else None
        except (TypeError, ValueError):
            raise PermissionDenied("Workspace non valido")
        if workspace_id is not None:
            _visible_workspace(request, workspace_id)
        colors = {**DEFAULT_COLORS}

        global_settings = BrandingSettings.objects.filter(workspace__isnull=True).order_by("id").first()
        if global_settings and global_settings.colors:
            colors.update(global_settings.colors)

        workspace_settings = None
        if workspace_id:
            workspace_settings = BrandingSettings.objects.filter(workspace_id=workspace_id).first()
            if workspace_settings and workspace_settings.colors:
                colors.update(workspace_settings.colors)

        logo_full = (
            workspace_settings.logo_full if workspace_settings and workspace_settings.logo_full else None
        ) or (global_settings.logo_full if global_settings else None)
        logo_compact = (
            workspace_settings.logo_compact if workspace_settings and workspace_settings.logo_compact else None
        ) or (global_settings.logo_compact if global_settings else None)
        favicon = (
            workspace_settings.favicon if workspace_settings and workspace_settings.favicon else None
        ) or (global_settings.favicon if global_settings else None)

        return Response(
            {
                "workspace_id": workspace_id,
                "colors": colors,
                "theme": _console_theme(colors),
                "logo_full": _file_url(request, logo_full),
                "logo_compact": _file_url(request, logo_compact),
                "favicon": _file_url(request, favicon),
            }
        )
