from rest_framework import serializers

from base_modules.ai_labs.models import Flow

from .models import Document, DocumentPermission, DocumentResult, DocumentVersion, Folder


class FolderSerializer(serializers.ModelSerializer):
    class Meta:
        model = Folder
        fields = ("id", "parent", "name", "created_at")
        read_only_fields = ("id", "created_at")


class DocumentVersionSerializer(serializers.ModelSerializer):
    class Meta:
        model = DocumentVersion
        fields = (
            "id", "version", "filename", "media_type", "size", "checksum", "page_count",
            "status", "error_message", "created_at",
        )
        read_only_fields = fields


class DocumentSerializer(serializers.ModelSerializer):
    versions = DocumentVersionSerializer(many=True, read_only=True)

    class Meta:
        model = Document
        fields = ("id", "folder", "title", "visibility", "versions", "created_at", "updated_at")
        read_only_fields = ("id", "versions", "created_at", "updated_at")


class DocumentCreateSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=500)
    visibility = serializers.ChoiceField(choices=Document.VISIBILITIES, default=Document.WORKSPACE)
    folder_id = serializers.IntegerField(min_value=1, required=False, allow_null=True)
    file = serializers.FileField()


class DocumentPermissionSerializer(serializers.ModelSerializer):
    class Meta:
        model = DocumentPermission
        fields = ("id", "user", "can_run", "can_chat")
        read_only_fields = ("id",)


class DocumentExtractSerializer(serializers.Serializer):
    pages = serializers.ListField(child=serializers.IntegerField(min_value=1), required=False)
    area = serializers.JSONField(required=False)


class DocumentRunSerializer(serializers.Serializer):
    flow_id = serializers.IntegerField(min_value=1)
    idempotency_key = serializers.CharField(max_length=160)
    pages = serializers.ListField(child=serializers.IntegerField(min_value=1), required=False)
    area = serializers.JSONField(required=False)

    def validate_flow_id(self, value):
        workspace = self.context["workspace"]
        if not Flow.objects.filter(pk=value, workspace=workspace, published_version__isnull=False).exists():
            raise serializers.ValidationError("Flow pubblicato non disponibile.")
        return value


class DocumentResultSerializer(serializers.ModelSerializer):
    run_status = serializers.CharField(source="run.status", read_only=True)

    class Meta:
        model = DocumentResult
        fields = ("id", "document_version", "flow_version", "run", "run_status", "result", "created_at")
        read_only_fields = fields

