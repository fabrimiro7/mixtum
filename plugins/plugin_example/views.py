from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from base_modules.workspace.permissions import HasSelectedWorkspace

from .models import ExampleModel
from .serializers import ExampleModelSerializer, ExampleModelWriteSerializer
from .services import ExampleModelService


class ExampleModelListView(APIView):
    """
    GET  /api/plugin-example/examples/  → lista
    POST /api/plugin-example/examples/  → crea
    """
    permission_classes = [IsAuthenticated, HasSelectedWorkspace]

    def get(self, request):
        items = ExampleModelService.get_list(workspace=request.workspace)
        return Response(ExampleModelSerializer(items, many=True).data)

    def post(self, request):
        serializer = ExampleModelWriteSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        item = ExampleModelService.create(
            data=serializer.validated_data,
            user=request.user,
            workspace=request.workspace,
        )
        return Response(ExampleModelSerializer(item).data, status=status.HTTP_201_CREATED)


class ExampleModelDetailView(APIView):
    """
    GET    /api/plugin-example/examples/<pk>/  → dettaglio
    PATCH  /api/plugin-example/examples/<pk>/  → aggiorna
    DELETE /api/plugin-example/examples/<pk>/  → elimina
    """
    permission_classes = [IsAuthenticated, HasSelectedWorkspace]

    def get_object(self, pk, workspace):
        return ExampleModelService.get_by_id(pk=pk, workspace=workspace)

    def get(self, request, pk):
        item = self.get_object(pk, request.workspace)
        return Response(ExampleModelSerializer(item).data)

    def patch(self, request, pk):
        item = self.get_object(pk, request.workspace)
        serializer = ExampleModelWriteSerializer(item, data=request.data, partial=True)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        item = ExampleModelService.update(
            instance=item,
            data=serializer.validated_data,
        )
        return Response(ExampleModelSerializer(item).data)

    def delete(self, request, pk):
        item = self.get_object(pk, request.workspace)
        ExampleModelService.delete(instance=item)
        return Response(status=status.HTTP_204_NO_CONTENT)
