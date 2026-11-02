from django.http import FileResponse, HttpResponse
from django.shortcuts import get_object_or_404
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from base_modules.ai_labs.models import Flow
from base_modules.ai_labs.serializers import RunSerializer
from base_modules.ai_labs.services import start_flow_run
from base_modules.ai_labs.tasks import execute_run_task
from base_modules.workspace.models import WorkspaceUser
from base_modules.workspace.permissions import HasManagedWorkspace, HasSelectedWorkspace

from .models import Document, DocumentPermission, DocumentVersion, Folder
from .serializers import (
    DocumentCreateSerializer, DocumentExtractSerializer, DocumentPermissionSerializer, DocumentRunSerializer,
    DocumentSerializer, FolderSerializer,
)
from .services import can_access_document, create_document, extract_version, visible_documents
from .pdf import render_pdf_page


class FolderViewSet(viewsets.ModelViewSet):
    serializer_class = FolderSerializer
    permission_classes = (IsAuthenticated, HasManagedWorkspace)

    def get_queryset(self):
        return Folder.objects.filter(workspace=self.request.workspace).order_by("name")

    def perform_create(self, serializer):
        parent = serializer.validated_data.get("parent")
        if parent is not None and parent.workspace_id != self.request.workspace.pk:
            raise PermissionDenied("Cartella padre di un altro workspace.")
        serializer.save(workspace=self.request.workspace)


class DocumentViewSet(viewsets.ModelViewSet):
    permission_classes = (IsAuthenticated, HasSelectedWorkspace)

    def get_serializer_class(self):
        return DocumentCreateSerializer if self.action == "create" else DocumentSerializer

    def get_queryset(self):
        return visible_documents(user=self.request.user, workspace=self.request.workspace).prefetch_related("versions")

    def create(self, request):
        serializer = DocumentCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        folder = None
        if serializer.validated_data.get("folder_id"):
            folder = get_object_or_404(
                Folder, pk=serializer.validated_data["folder_id"], workspace=request.workspace,
            )
        document = create_document(
            workspace=request.workspace, actor=request.user, folder=folder,
            title=serializer.validated_data["title"], visibility=serializer.validated_data["visibility"],
            upload=serializer.validated_data["file"],
        )
        return Response(DocumentSerializer(document).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=("get",), url_path=r"versions/(?P<version_id>[^/.]+)/download")
    def download(self, request, pk=None, version_id=None):
        document = self.get_object()
        version = get_object_or_404(document.versions, pk=version_id)
        response = FileResponse(version.file.open("rb"), content_type=version.media_type, as_attachment=False)
        response["Content-Disposition"] = f'inline; filename="{version.filename.replace(chr(34), "")}"'
        response["X-Content-Type-Options"] = "nosniff"
        response["Cache-Control"] = "private, no-store"
        return response

    @action(detail=True, methods=("post",), url_path=r"versions/(?P<version_id>[^/.]+)/extract")
    def extract(self, request, pk=None, version_id=None):
        document = self.get_object()
        if not can_access_document(document=document, user=request.user, operation="run"):
            raise PermissionDenied("Permesso di elaborazione documento mancante.")
        version = get_object_or_404(document.versions, pk=version_id)
        serializer = DocumentExtractSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        chunks = extract_version(version, **serializer.validated_data)
        return Response({"chunks": chunks})

    @action(detail=True, methods=("get",), url_path=r"versions/(?P<version_id>[^/.]+)/pages/(?P<page_number>[^/.]+)")
    def page_image(self, request, pk=None, version_id=None, page_number=None):
        document = self.get_object()
        version = get_object_or_404(document.versions, pk=version_id, status=DocumentVersion.READY)
        with version.file.open("rb") as handle:
            image = render_pdf_page(handle.read(), int(page_number))
        response = HttpResponse(image, content_type="image/png")
        response["Cache-Control"] = "private, no-store"
        response["X-Content-Type-Options"] = "nosniff"
        return response

    @action(detail=True, methods=("post",), url_path=r"versions/(?P<version_id>[^/.]+)/runs")
    def run_flow(self, request, pk=None, version_id=None):
        document = self.get_object()
        if not can_access_document(document=document, user=request.user, operation="run"):
            raise PermissionDenied("Permesso di elaborazione documento mancante.")
        version = get_object_or_404(document.versions, pk=version_id, status=DocumentVersion.READY)
        serializer = DocumentRunSerializer(data=request.data, context={"workspace": request.workspace})
        serializer.is_valid(raise_exception=True)
        flow = Flow.objects.select_related("published_version").get(pk=serializer.validated_data["flow_id"])
        run, created = start_flow_run(
            flow=flow, actor=request.user, idempotency_key=serializer.validated_data["idempotency_key"],
            source_product="documents", input_data={
                "document_version_id": version.pk,
                "pages": serializer.validated_data.get("pages"),
                "area": serializer.validated_data.get("area"),
            },
        )
        if created:
            execute_run_task.delay(str(run.pk))
        return Response(RunSerializer(run).data, status=status.HTTP_202_ACCEPTED if created else status.HTTP_200_OK)

    @action(detail=True, methods=("get", "post"), permission_classes=(IsAuthenticated, HasManagedWorkspace))
    def permissions(self, request, pk=None):
        document = get_object_or_404(Document, pk=pk, workspace=request.workspace)
        if request.method == "GET":
            return Response(DocumentPermissionSerializer(document.permissions.all(), many=True).data)
        serializer = DocumentPermissionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data["user"]
        if not WorkspaceUser.objects.filter(workspace=request.workspace, user=user).exists():
            raise PermissionDenied("L'utente non appartiene al workspace.")
        permission, _ = DocumentPermission.objects.update_or_create(
            document=document, user=user,
            defaults={
                "can_run": serializer.validated_data.get("can_run", False),
                "can_chat": serializer.validated_data.get("can_chat", False),
            },
        )
        return Response(DocumentPermissionSerializer(permission).data, status=status.HTTP_201_CREATED)
