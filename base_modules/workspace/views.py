from base_modules.user_manager.models import User
from rest_framework import permissions, viewsets
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Workspace, WorkspaceUser
from .serializers import UserSerializer, WorkspaceSerializer, WorkspaceUserSerializer


class SessionView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        memberships = WorkspaceUser.objects.select_related("workspace").filter(user=request.user).order_by("workspace_id")
        return Response({
            "user": UserSerializer(request.user).data,
            "workspaces": [
                {"id": membership.workspace_id, "name": membership.workspace.workspace_name, "role": membership.role}
                for membership in memberships
            ],
        })


class UserViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        if self.request.user.is_staff:
            return User.objects.all()
        return User.objects.filter(pk=self.request.user.pk)


class WorkspaceViewSet(viewsets.ModelViewSet):
    serializer_class = WorkspaceSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_permissions(self):
        if self.action not in ("list", "retrieve"):
            return [permissions.IsAdminUser()]
        return super().get_permissions()

    def get_queryset(self):
        if self.request.user.is_staff:
            return Workspace.objects.all()
        return Workspace.objects.filter(workspaceuser__user=self.request.user).distinct()


class WorkspaceUserViewSet(viewsets.ModelViewSet):
    serializer_class = WorkspaceUserSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_permissions(self):
        if self.action not in ("list", "retrieve"):
            return [permissions.IsAdminUser()]
        return super().get_permissions()

    def get_queryset(self):
        queryset = WorkspaceUser.objects.select_related("workspace", "user")
        if self.request.user.is_staff:
            return queryset
        return queryset.filter(user=self.request.user)
