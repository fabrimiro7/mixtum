from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from base_modules.workspace.permissions import HasSelectedWorkspace


@api_view(["GET"])
@permission_classes([IsAuthenticated, HasSelectedWorkspace])
def status(request):
    return Response({"workspace_id": request.workspace.id, "plugin": "external_probe"})
