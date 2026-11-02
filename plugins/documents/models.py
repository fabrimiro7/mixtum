from django.conf import settings
from django.db import models


class Folder(models.Model):
    workspace = models.ForeignKey("workspace.Workspace", on_delete=models.CASCADE, related_name="document_folders")
    parent = models.ForeignKey("self", on_delete=models.CASCADE, null=True, blank=True, related_name="children")
    name = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=("workspace", "parent", "name"), name="documents_folder_name_uniq")]


class Document(models.Model):
    WORKSPACE = "workspace"
    RESTRICTED = "restricted"
    VISIBILITIES = ((WORKSPACE, "Workspace"), (RESTRICTED, "Restricted"))

    workspace = models.ForeignKey("workspace.Workspace", on_delete=models.CASCADE, related_name="documents")
    folder = models.ForeignKey(Folder, on_delete=models.SET_NULL, null=True, blank=True, related_name="documents")
    title = models.CharField(max_length=500)
    visibility = models.CharField(max_length=16, choices=VISIBILITIES, default=WORKSPACE)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="created_documents")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class DocumentPermission(models.Model):
    document = models.ForeignKey(Document, on_delete=models.CASCADE, related_name="permissions")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="document_permissions")
    can_run = models.BooleanField(default=False)
    can_chat = models.BooleanField(default=False)

    class Meta:
        constraints = [models.UniqueConstraint(fields=("document", "user"), name="documents_permission_user_uniq")]


class DocumentVersion(models.Model):
    UPLOADED = "uploaded"
    READY = "ready"
    FAILED = "failed"
    STATUSES = ((UPLOADED, "Uploaded"), (READY, "Ready"), (FAILED, "Failed"))

    document = models.ForeignKey(Document, on_delete=models.CASCADE, related_name="versions")
    version = models.PositiveIntegerField()
    file = models.FileField(upload_to="documents/private/")
    filename = models.CharField(max_length=500)
    media_type = models.CharField(max_length=120)
    size = models.PositiveBigIntegerField()
    checksum = models.CharField(max_length=64)
    page_count = models.PositiveIntegerField(null=True, blank=True)
    status = models.CharField(max_length=16, choices=STATUSES, default=UPLOADED)
    error_message = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=("document", "version"), name="documents_version_uniq")]


class DocumentResult(models.Model):
    document_version = models.ForeignKey(DocumentVersion, on_delete=models.PROTECT, related_name="results")
    flow_version = models.ForeignKey("ai_labs.FlowVersion", on_delete=models.PROTECT, related_name="document_results")
    run = models.OneToOneField("ai_labs.Run", on_delete=models.PROTECT, related_name="document_result")
    result = models.JSONField(default=dict)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)

