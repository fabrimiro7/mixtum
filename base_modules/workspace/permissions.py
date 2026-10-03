from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import BasePermission

from .models import WorkspaceUser


class HasSelectedWorkspace(BasePermission):
    """Resolve a workspace only after DRF has authenticated the request."""

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        raw_id = request.headers.get("X-Workspace-Id")
        if (
            not raw_id or not raw_id.isascii() or not raw_id.isdecimal()
            or len(raw_id) > 19
        ):
            raise ValidationError({"detail": "X-Workspace-Id richiesto e non valido."})

        workspace_id = int(raw_id)
        # Workspace uses BigAutoField; reject values PostgreSQL cannot represent before querying.
        if not 0 < workspace_id <= 9223372036854775807:
            raise ValidationError({"detail": "X-Workspace-Id richiesto e non valido."})

        membership = WorkspaceUser.objects.select_related("workspace").filter(
            user=request.user, workspace_id=workspace_id
        ).first()
        if membership is None:
            raise PermissionDenied("Workspace non valido o accesso negato.")

        request.workspace = membership.workspace
        return True
