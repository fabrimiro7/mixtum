from celery import shared_task
from datetime import timedelta
from django.utils import timezone

from .services import execute_run
from .knowledge import index_revision
from .models import RunEvent, WorkspaceAiPolicy


@shared_task(bind=True, autoretry_for=(), max_retries=0, soft_time_limit=1800, time_limit=1860)
def execute_run_task(self, run_id):
    execute_run(run_id)


@shared_task(bind=True, autoretry_for=(), max_retries=0, soft_time_limit=3600, time_limit=3660)
def index_revision_task(self, revision_id):
    index_revision(revision_id)


@shared_task
def purge_ai_diagnostics():
    now = timezone.now()
    RunEvent.objects.filter(debug_expires_at__lte=now).update(debug_content=None, debug_expires_at=None)
    for policy in WorkspaceAiPolicy.objects.iterator():
        cutoff = now - timedelta(days=policy.metadata_retention_days)
        RunEvent.objects.filter(run__workspace=policy.workspace, created_at__lt=cutoff).delete()
