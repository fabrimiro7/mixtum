from base_modules.ai_labs.models import KnowledgeSource
from base_modules.ai_labs.registry import (
    SourceContract, ToolContract, register_run_observer, register_source, register_tool,
)
from rest_framework.exceptions import PermissionDenied, ValidationError

from .models import DocumentResult, DocumentVersion
from .services import can_access_document, extract_version


def _version_for_source(source):
    version = DocumentVersion.objects.select_related("document").filter(
        pk=source.resource_id, document__workspace=source.knowledge_base.workspace,
    ).first()
    if version is None:
        raise ValidationError("Versione Documents non disponibile nel workspace.")
    return version


def extract_source(*, source):
    return extract_version(_version_for_source(source))


def can_access_source(*, source, user):
    try:
        version = _version_for_source(source)
    except ValidationError:
        return False
    return can_access_document(document=version.document, user=user, operation="view")


def extract_tool(*, actor, workspace, input_data, run):
    version = DocumentVersion.objects.select_related("document").filter(
        pk=input_data["document_version_id"], document__workspace=workspace,
    ).first()
    if version is None or not can_access_document(document=version.document, user=actor, operation="run"):
        raise PermissionDenied("Documento non disponibile per l'elaborazione.")
    return {"chunks": extract_version(version, pages=input_data.get("pages"), area=input_data.get("area"))}


register_source(SourceContract(key="documents.version", extract=extract_source, can_access=can_access_source))
register_tool(ToolContract(
    key="documents.extract", handler=extract_tool,
    input_schema={
        "type": "object", "required": ["document_version_id"],
        "properties": {
            "document_version_id": {"type": "integer"},
            "pages": {"type": ["array", "null"], "items": {"type": "integer"}},
            "area": {"type": ["object", "null"]},
        },
    },
    output_schema={"type": "object", "required": ["chunks"], "properties": {"chunks": {"type": "array"}}},
))


def store_document_result(*, run):
    if run.source_product != "documents" or not run.flow_version_id:
        return
    version = DocumentVersion.objects.filter(
        pk=(run.input or {}).get("document_version_id"), document__workspace=run.workspace,
    ).first()
    if version is None:
        return
    DocumentResult.objects.update_or_create(
        run=run,
        defaults={
            "document_version": version, "flow_version": run.flow_version,
            "result": run.output, "created_by": run.created_by,
        },
    )


register_run_observer("documents.result", store_document_result)
