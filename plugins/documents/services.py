import hashlib
import mimetypes
from pathlib import Path

from django.db import transaction
from django.db.models import Max, Q
from rest_framework.exceptions import PermissionDenied, ValidationError

from base_modules.workspace.models import WorkspaceUser

from .models import Document, DocumentPermission, DocumentVersion
from .pdf import extract_pdf, inspect_pdf


MAX_DOCUMENT_BYTES = 50 * 1024 * 1024
ALLOWED_EXTENSIONS = {".pdf", ".txt", ".html", ".htm", ".png", ".jpg", ".jpeg"}


def visible_documents(*, user, workspace):
    base = Document.objects.filter(workspace=workspace)
    if user.is_superuser or WorkspaceUser.objects.filter(user=user, workspace=workspace, role=WorkspaceUser.OWNER).exists():
        return base
    return base.filter(
        Q(visibility=Document.WORKSPACE) | Q(created_by=user) | Q(permissions__user=user),
    ).distinct()


def can_access_document(*, document, user, operation="view"):
    if not visible_documents(user=user, workspace=document.workspace).filter(pk=document.pk).exists():
        return False
    if operation == "view" or document.created_by_id == user.pk or user.is_superuser:
        return True
    if WorkspaceUser.objects.filter(user=user, workspace=document.workspace, role=WorkspaceUser.OWNER).exists():
        return True
    permission = DocumentPermission.objects.filter(document=document, user=user).first()
    return bool(permission and getattr(permission, f"can_{operation}", False))


@transaction.atomic
def create_document(*, workspace, actor, title, visibility, upload, folder=None):
    if folder is not None and folder.workspace_id != workspace.pk:
        raise ValidationError({"folder": "Cartella di un altro workspace."})
    suffix = Path(upload.name).suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise ValidationError({"file": "Formato non supportato."})
    if upload.size <= 0 or upload.size > MAX_DOCUMENT_BYTES:
        raise ValidationError({"file": "Dimensione file non valida (massimo 50 MiB)."})
    digest = hashlib.sha256()
    for chunk in upload.chunks():
        digest.update(chunk)
    upload.seek(0)
    document = Document.objects.create(
        workspace=workspace, folder=folder, title=title, visibility=visibility, created_by=actor,
    )
    media_type = mimetypes.guess_type(upload.name)[0] or "application/octet-stream"
    version = DocumentVersion.objects.create(
        document=document, version=1, file=upload, filename=Path(upload.name).name,
        media_type=media_type, size=upload.size, checksum=digest.hexdigest(),
    )
    if suffix == ".pdf":
        try:
            with version.file.open("rb") as handle:
                version.page_count = inspect_pdf(handle.read(MAX_DOCUMENT_BYTES + 1))
            version.status = DocumentVersion.READY
        except ValidationError as exc:
            version.status = DocumentVersion.FAILED
            version.error_message = str(exc)
    elif suffix in {".txt", ".html", ".htm"}:
        version.page_count = 1
        version.status = DocumentVersion.READY
    else:
        version.page_count = 1
        version.status = DocumentVersion.READY
    version.save(update_fields=("page_count", "status", "error_message"))
    return document


def extract_version(version, *, pages=None, area=None):
    suffix = Path(version.filename).suffix.lower()
    if version.status != DocumentVersion.READY:
        raise ValidationError("Versione documento non elaborabile.")
    if suffix == ".pdf":
        with version.file.open("rb") as handle:
            chunks = list(extract_pdf(handle.read(MAX_DOCUMENT_BYTES + 1), pages=pages, area=area))
        for chunk in chunks:
            chunk["metadata"]["filename"] = version.filename
        return chunks
    if pages not in (None, [1]) or area is not None:
        raise ValidationError("Pagine e aree sono disponibili solo per PDF.")
    if suffix in {".txt", ".html", ".htm"}:
        with version.file.open("rb") as handle:
            try:
                text = handle.read(MAX_DOCUMENT_BYTES + 1).decode("utf-8")
            except UnicodeDecodeError as exc:
                raise ValidationError("Documento testuale non UTF-8.") from exc
        return [{"text": text, "page": 1, "area": None, "metadata": {"filename": version.filename}}]
    raise ValidationError("L'immagine richiede un nodo OCR o vision configurato; nessun fallback simulato è disponibile.")
