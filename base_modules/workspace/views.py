from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models import Q
from rest_framework import permissions, status, viewsets
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from base_modules.user_manager.models import User

from .models import AdminAuditEvent, Workspace, WorkspaceUser
from .permissions import CanManageWorkspaceObject, IsPlatformAdmin
from .serializers import UserSerializer, WorkspaceSerializer, WorkspaceUserSerializer
from .services import delete_membership, record_admin_event


class SessionView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        memberships = list(
            WorkspaceUser.objects.select_related("workspace").filter(user=request.user).order_by("workspace_id")
        )
        membership_by_workspace = {membership.workspace_id: membership for membership in memberships}
        if request.user.is_superuser:
            workspaces = list(Workspace.objects.all().order_by("id"))
        else:
            workspaces = [membership.workspace for membership in memberships]
        owned_workspace_ids = [
            membership.workspace_id
            for membership in memberships
            if membership.role == WorkspaceUser.OWNER
        ]
        return Response({
            "user": UserSerializer(request.user).data,
            "workspaces": [
                {
                    "id": workspace.pk,
                    "name": workspace.workspace_name,
                    "role": (
                        membership_by_workspace[workspace.pk].role
                        if workspace.pk in membership_by_workspace else None
                    ),
                    "can_manage": request.user.is_superuser or (
                        workspace.pk in membership_by_workspace
                        and membership_by_workspace[workspace.pk].role == WorkspaceUser.OWNER
                    ),
                }
                for workspace in workspaces
            ],
            "capabilities": {
                "platform_admin": request.user.is_superuser,
                "manage_global_branding": request.user.is_superuser,
                "managed_workspace_ids": owned_workspace_ids,
            },
        })


class UserViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        if self.request.user.is_superuser:
            return User.objects.filter(is_active=True, external_identity__isnull=False).distinct()
        return User.objects.filter(pk=self.request.user.pk)


class WorkspaceViewSet(viewsets.ModelViewSet):
    serializer_class = WorkspaceSerializer
    permission_classes = [permissions.IsAuthenticated]
    http_method_names = ["get", "post", "patch", "head", "options"]

    def get_permissions(self):
        if self.action == "create":
            return [IsPlatformAdmin()]
        if self.action in ("update", "partial_update"):
            return [permissions.IsAuthenticated(), CanManageWorkspaceObject()]
        return super().get_permissions()

    def get_queryset(self):
        if self.request.user.is_superuser:
            return Workspace.objects.all()
        return Workspace.objects.filter(workspaceuser__user=self.request.user).distinct()

    def perform_create(self, serializer):
        workspace = serializer.save()
        record_admin_event(
            actor=self.request.user,
            action="workspace.create",
            outcome=AdminAuditEvent.SUCCESS,
            workspace=workspace,
            target_user=serializer.validated_data["owner"],
        )

    def perform_update(self, serializer):
        workspace = serializer.save()
        record_admin_event(
            actor=self.request.user,
            action="workspace.update",
            outcome=AdminAuditEvent.SUCCESS,
            workspace=workspace,
        )


class WorkspaceUserViewSet(viewsets.ModelViewSet):
    serializer_class = WorkspaceUserSerializer
    permission_classes = [permissions.IsAuthenticated]
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]

    def get_permissions(self):
        if self.action == "create":
            return [IsPlatformAdmin()]
        if self.action in ("update", "partial_update", "destroy"):
            return [permissions.IsAuthenticated(), CanManageWorkspaceObject()]
        return super().get_permissions()

    def get_queryset(self):
        queryset = WorkspaceUser.objects.select_related("workspace", "user")
        if self.request.user.is_superuser:
            return queryset
        owned_workspace_ids = WorkspaceUser.objects.filter(
            user=self.request.user, role=WorkspaceUser.OWNER,
        ).values("workspace_id")
        return queryset.filter(
            Q(workspace_id__in=owned_workspace_ids) | Q(user=self.request.user)
        ).distinct()

    def perform_create(self, serializer):
        membership = serializer.save()
        record_admin_event(
            actor=self.request.user,
            action="workspace.membership.create",
            outcome=AdminAuditEvent.SUCCESS,
            workspace=membership.workspace,
            target_user=membership.user,
        )

    def update(self, request, *args, **kwargs):
        membership = self.get_object()
        try:
            return super().update(request, *args, **kwargs)
        except ValidationError:
            record_admin_event(
                actor=request.user,
                action="workspace.membership.update",
                outcome=AdminAuditEvent.DENIED,
                workspace=membership.workspace,
                target_user=membership.user,
            )
            raise

    def perform_update(self, serializer):
        membership = serializer.save()
        record_admin_event(
            actor=self.request.user,
            action="workspace.membership.update",
            outcome=AdminAuditEvent.SUCCESS,
            workspace=membership.workspace,
            target_user=membership.user,
        )

    def destroy(self, request, *args, **kwargs):
        membership = self.get_object()
        workspace = membership.workspace
        target_user = membership.user
        try:
            delete_membership(membership=membership)
        except DjangoValidationError as error:
            record_admin_event(
                actor=request.user,
                action="workspace.membership.delete",
                outcome=AdminAuditEvent.DENIED,
                workspace=workspace,
                target_user=target_user,
            )
            raise ValidationError(error.messages) from None
        record_admin_event(
            actor=request.user,
            action="workspace.membership.delete",
            outcome=AdminAuditEvent.SUCCESS,
            workspace=workspace,
            target_user=target_user,
        )
        return Response(status=status.HTTP_204_NO_CONTENT)
