from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import BasePermission

from .models import Workspace, WorkspaceUser


def selected_workspace_id(request):
    raw_id = request.headers.get("X-Workspace-Id")
    if (
        not raw_id or not raw_id.isascii() or not raw_id.isdecimal()
        or len(raw_id) > 19
    ):
        raise ValidationError({"detail": "X-Workspace-Id richiesto e non valido."})

    workspace_id = int(raw_id)
    if not 0 < workspace_id <= 9223372036854775807:
        raise ValidationError({"detail": "X-Workspace-Id richiesto e non valido."})
    return workspace_id


class IsPlatformAdmin(BasePermission):
    def has_permission(self, request, view):
        user = getattr(request, "user", None)
        return bool(user and user.is_authenticated and user.is_superuser)


class CanManageWorkspaceObject(BasePermission):
    def has_object_permission(self, request, view, obj):
        if request.user.is_superuser:
            return True
        workspace_id = obj.workspace_id if isinstance(obj, WorkspaceUser) else obj.pk
        return WorkspaceUser.objects.filter(
            user=request.user, workspace_id=workspace_id, role=WorkspaceUser.OWNER,
        ).exists()


class HasManagedWorkspace(BasePermission):
    """Resolve a selected workspace for a platform admin or its explicit owner."""

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        workspace_id = selected_workspace_id(request)
        if request.user.is_superuser:
            workspace = Workspace.objects.filter(pk=workspace_id).first()
        else:
            membership = WorkspaceUser.objects.select_related("workspace").filter(
                user=request.user, workspace_id=workspace_id, role=WorkspaceUser.OWNER,
            ).first()
            workspace = membership.workspace if membership else None
        if workspace is None:
            raise PermissionDenied("Workspace non valido o accesso negato.")
        request.workspace = workspace
        return True


class HasSelectedWorkspace(BasePermission):
    """Resolve a workspace only after DRF has authenticated the request."""

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        workspace_id = selected_workspace_id(request)

        membership = WorkspaceUser.objects.select_related("workspace").filter(
            user=request.user, workspace_id=workspace_id
        ).first()
        if membership is None:
            raise PermissionDenied("Workspace non valido o accesso negato.")

        request.workspace = membership.workspace
        return True
