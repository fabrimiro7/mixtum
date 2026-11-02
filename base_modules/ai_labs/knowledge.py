import hashlib
from pathlib import Path

from django.db import transaction
from django.db.models import Max
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError

from .accounting import reconcile_budget, reserve_budget
from .models import KnowledgeChunk, KnowledgeRevision, KnowledgeSource, Run
from .providers import client_for_model, estimate_tokens
from .registry import get_source
from .services import _event
from .vector_store import QdrantStore, collection_name


ALLOWED_UPLOAD_TYPES = {"text/plain", "text/html"}
MAX_SOURCE_BYTES = 25 * 1024 * 1024


def _split_text(text, *, page=None, metadata=None, size=1800, overlap=180):
    if not isinstance(text, str):
        raise ValidationError("Contenuto sorgente non testuale.")
    clean = text.strip()
    chunks = []
    start = 0
    while start < len(clean):
        end = min(start + size, len(clean))
        if end < len(clean):
            boundary = clean.rfind("\n", start + size // 2, end)
            if boundary > start:
                end = boundary
        value = clean[start:end].strip()
        if value:
            chunks.append({"text": value, "page": page, "area": None, "metadata": metadata or {}})
        if end >= len(clean):
            break
        start = max(end - overlap, start + 1)
    return chunks


def _extract_upload(source):
    if not source.uploaded_file:
        raise ValidationError("File sorgente mancante.")
    if source.uploaded_file.size > MAX_SOURCE_BYTES:
        raise ValidationError("File sorgente oltre il limite di 25 MiB.")
    suffix = Path(source.uploaded_file.name).suffix.lower()
    if suffix not in {".txt", ".html", ".htm"}:
        raise ValidationError("AI Labs accetta direttamente testo e HTML; i documenti sono forniti dal prodotto Documents.")
    with source.uploaded_file.open("rb") as handle:
        content = handle.read(MAX_SOURCE_BYTES + 1)
    if len(content) > MAX_SOURCE_BYTES:
        raise ValidationError("File sorgente oltre il limite di 25 MiB.")
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValidationError("Il file deve essere UTF-8.") from exc
    return _split_text(text, metadata={"filename": Path(source.uploaded_file.name).name})


def extract_source(source):
    if source.source_type == KnowledgeSource.UPLOAD:
        return _extract_upload(source)
    contract = get_source(source.adapter_key)
    return contract.extract(source=source)


def can_access_source(source, user):
    if source.source_type == KnowledgeSource.UPLOAD:
        return source.visibility == KnowledgeSource.WORKSPACE or source.created_by_id == user.pk
    return bool(get_source(source.adapter_key).can_access(source=source, user=user))


@transaction.atomic
def create_revision(source):
    locked = KnowledgeSource.objects.select_for_update().select_related("knowledge_base").get(pk=source.pk)
    chunks = extract_source(locked)
    digest = hashlib.sha256()
    for chunk in chunks:
        digest.update(chunk["text"].encode("utf-8"))
        digest.update(str(chunk.get("page") or "").encode("ascii"))
    version = (locked.revisions.aggregate(value=Max("version"))["value"] or 0) + 1
    revision = KnowledgeRevision.objects.create(
        source=locked, version=version, checksum=digest.hexdigest(),
        index_generation=locked.knowledge_base.index_generation,
    )
    KnowledgeChunk.objects.bulk_create([
        KnowledgeChunk(
            revision=revision, ordinal=index, text=chunk["text"], page=chunk.get("page"),
            area=chunk.get("area"), metadata=chunk.get("metadata") or {},
        )
        for index, chunk in enumerate(chunks)
    ])
    return revision


def index_revision(revision_id, *, store=None):
    revision = KnowledgeRevision.objects.select_related(
        "source__knowledge_base__embedding_model__provider", "source__knowledge_base__workspace", "source__created_by",
    ).get(pk=revision_id)
    kb = revision.source.knowledge_base
    if revision.index_generation != kb.index_generation:
        raise ValidationError("La revisione appartiene a una generazione indice obsoleta.")
    run = Run.objects.create(
        kind=Run.INGESTION, workspace=kb.workspace, created_by=revision.source.created_by,
        source_product="ai_labs_ingestion", idempotency_key=f"revision:{revision.pk}:generation:{revision.index_generation}",
        input={"revision_id": revision.pk}, status=Run.RUNNING, started_at=timezone.now(),
    )
    revision.status = KnowledgeRevision.INDEXING
    revision.save(update_fields=("status",))
    _event(run, "ingestion.started", metadata={"revision": revision.pk, "knowledge_base": kb.pk})
    try:
        chunks = list(revision.chunks.all())
        texts = [chunk.text for chunk in chunks]
        estimated = sum(estimate_tokens([{"content": text}], 0) for text in texts)
        reservation = reserve_budget(run=run, key="embedding", estimated_tokens=estimated, estimated_cost_microunits=None)
        vectors, actual_tokens, latency_ms = client_for_model(kb.embedding_model).embed(model=kb.embedding_model, inputs=texts)
        if any(len(vector) != kb.vector_size for vector in vectors):
            raise ValidationError("Dimensione embedding diversa da quella configurata.")
        points = [
            {"id": str(chunk.vector_point_id), "vector": vector,
             "payload": {"workspace_id": kb.workspace_id, "knowledge_base_id": kb.pk,
                         "revision_id": revision.pk, "generation": kb.index_generation}}
            for chunk, vector in zip(chunks, vectors, strict=True)
        ]
        store = store or QdrantStore()
        name = collection_name(kb)
        store.ensure_collection(name, kb.vector_size)
        store.upsert(name, points)
        reconcile_budget(reservation, actual_tokens=actual_tokens, actual_cost_microunits=None)
        revision.status = KnowledgeRevision.READY
        revision.indexed_at = timezone.now()
        revision.save(update_fields=("status", "indexed_at"))
        run.status = Run.COMPLETED
        run.total_tokens = actual_tokens
        run.ended_at = timezone.now()
        run.output = {"revision_id": revision.pk, "chunks": len(chunks)}
        run.save(update_fields=("status", "total_tokens", "ended_at", "output", "updated_at"))
        _event(run, "ingestion.completed", metadata={"chunks": len(chunks), "latency_ms": latency_ms})
    except Exception as exc:
        revision.status = KnowledgeRevision.FAILED
        revision.error_message = str(exc)[:2000]
        revision.save(update_fields=("status", "error_message"))
        run.status = Run.FAILED
        run.error_code = type(exc).__name__
        run.error_message = str(exc)[:2000]
        run.ended_at = timezone.now()
        run.save(update_fields=("status", "error_code", "error_message", "ended_at", "updated_at"))
        _event(run, "ingestion.failed", metadata={"error_code": run.error_code, "message": run.error_message})
        raise
    return revision


def search_knowledge_base(*, knowledge_base, user, query, limit=8, store=None, run=None, reservation_key="retrieval"):
    if not query.strip():
        raise ValidationError("Query obbligatoria.")
    estimated_tokens = estimate_tokens([{"content": query}], 0)
    reservation = reserve_budget(
        run=run, key=reservation_key, estimated_tokens=estimated_tokens,
        estimated_cost_microunits=(
            int(knowledge_base.embedding_model.prompt_cost_per_million * estimated_tokens)
            if knowledge_base.embedding_model.prompt_cost_per_million is not None else None
        ),
    ) if run is not None else None
    vectors, actual_tokens, latency_ms = client_for_model(knowledge_base.embedding_model).embed(
        model=knowledge_base.embedding_model, inputs=[query],
    )
    if reservation is not None:
        actual_cost = (
            int(knowledge_base.embedding_model.prompt_cost_per_million * actual_tokens)
            if actual_tokens is not None and knowledge_base.embedding_model.prompt_cost_per_million is not None else None
        )
        reconcile_budget(reservation, actual_tokens=actual_tokens, actual_cost_microunits=actual_cost)
        _event(run, "retrieval.embedding", metadata={
            "knowledge_base": knowledge_base.pk, "tokens": actual_tokens, "latency_ms": latency_ms,
        })
    store = store or QdrantStore()
    hits = store.search(collection_name(knowledge_base), vectors[0], min(limit * 4, 50))
    point_scores = {str(hit.get("id")): hit.get("score") for hit in hits}
    chunks = KnowledgeChunk.objects.filter(
        vector_point_id__in=point_scores,
        revision__status=KnowledgeRevision.READY,
        revision__index_generation=knowledge_base.index_generation,
        revision__source__knowledge_base=knowledge_base,
    ).select_related("revision__source")
    authorized = []
    for chunk in chunks:
        if can_access_source(chunk.revision.source, user):
            authorized.append({
                "chunk_id": chunk.pk, "source_id": chunk.revision.source_id,
                "revision_id": chunk.revision_id, "title": chunk.revision.source.title,
                "page": chunk.page, "area": chunk.area, "text": chunk.text,
                "score": point_scores[str(chunk.vector_point_id)], "trust": "untrusted_source",
            })
    return sorted(authorized, key=lambda item: item["score"], reverse=True)[:limit]
