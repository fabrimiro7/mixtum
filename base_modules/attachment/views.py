from pathlib import PurePosixPath

from django.http import FileResponse, Http404
from .models import Attachment
from base_modules.user_manager.authentication import JWTAuthentication
from rest_framework.response import Response
from rest_framework import status, generics, permissions
from mixtum_core.settings.base import REMOTE_API
from .serializers import AttachmentEditSerializer, AttachmentSerializer


class AuthorScopedAttachmentMixin:
    permission_classes = [permissions.IsAuthenticated]
    if REMOTE_API:
        authentication_classes = [JWTAuthentication]

    def get_queryset(self):
        return Attachment.objects.filter(author=self.request.user).select_related("author")


class AttachmentCreateView(AuthorScopedAttachmentMixin, generics.CreateAPIView):
    serializer_class = AttachmentEditSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        attachment = serializer.save(author=request.user)
        return Response({
            "Attachment": AttachmentSerializer(attachment, context={"request": request}).data,
            "message": "success",
        }, status=status.HTTP_201_CREATED)

class AttachmentDeleteView(AuthorScopedAttachmentMixin, generics.DestroyAPIView):
    serializer_class = AttachmentSerializer

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        self.perform_destroy(instance)
        return Response({"message": "success"}, status=status.HTTP_204_NO_CONTENT)

class AttachmentUpdateView(AuthorScopedAttachmentMixin, generics.UpdateAPIView):
    serializer_class = AttachmentEditSerializer

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)

        self.perform_update(serializer)

        return Response({
            "Attachment": AttachmentSerializer(instance, context={"request": request}).data,
            "message": "success",
        }, status=status.HTTP_200_OK)

class AttachmentListView(AuthorScopedAttachmentMixin, generics.ListAPIView):
    serializer_class = AttachmentSerializer


class AttachmentDetailView(AuthorScopedAttachmentMixin, generics.RetrieveAPIView):
    serializer_class = AttachmentSerializer

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        return Response(serializer.data, status=status.HTTP_200_OK)


class AttachmentDownloadView(AuthorScopedAttachmentMixin, generics.GenericAPIView):
    def get(self, request, *args, **kwargs):
        attachment = self.get_object()
        if not attachment.file:
            raise Http404
        try:
            source = attachment.file.open("rb")
        except FileNotFoundError as exc:
            raise Http404 from exc
        filename = PurePosixPath(attachment.file.name.replace("\\", "/")).name
        response = FileResponse(source, as_attachment=True, filename=filename, content_type="application/octet-stream")
        response["Cache-Control"] = "private, no-store"
        response["X-Content-Type-Options"] = "nosniff"
        return response
