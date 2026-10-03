from rest_framework import mixins, viewsets
from rest_framework.permissions import IsAuthenticated

from base_modules.workspace.permissions import HasSelectedWorkspace

from .models import Item
from .serializers import ItemSerializer


class ItemViewSet(mixins.ListModelMixin, mixins.CreateModelMixin,
                  mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    serializer_class = ItemSerializer
    permission_classes = (IsAuthenticated, HasSelectedWorkspace)

    def get_queryset(self):
        return Item.objects.filter(workspace=self.request.workspace)

    def perform_create(self, serializer):
        serializer.save(workspace=self.request.workspace, created_by=self.request.user)
