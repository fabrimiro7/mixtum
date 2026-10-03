from rest_framework import filters, viewsets
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from base_modules.workspace.permissions import HasSelectedWorkspace

from .models import Link
from .serializers import LinkSerializer
from .filters import LinkFilter


class LinkViewSet(viewsets.ModelViewSet):
    queryset = Link.objects.all()
    serializer_class = LinkSerializer
    permission_classes = [IsAuthenticated, HasSelectedWorkspace]

    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = LinkFilter
    search_fields = ("title", "description", "url")
    ordering_fields = ("created_at", "label", "title")
    ordering = ("-created_at",)

    def get_queryset(self):
        return super().get_queryset().filter(workspace=self.request.workspace)

    def perform_create(self, serializer):
        serializer.save(workspace=self.request.workspace)
