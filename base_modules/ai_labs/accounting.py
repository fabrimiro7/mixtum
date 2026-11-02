from datetime import date

from django.db import transaction
from django.db.models import Case, F, IntegerField, Q, Sum, When
from rest_framework.exceptions import ValidationError

from .models import BudgetReservation, WorkspaceAiPolicy


def period_start(today=None):
    today = today or date.today()
    return today.replace(day=1)


@transaction.atomic
def reserve_budget(*, run, key, estimated_tokens, estimated_cost_microunits):
    policy, _ = WorkspaceAiPolicy.objects.get_or_create(workspace=run.workspace)
    policy = WorkspaceAiPolicy.objects.select_for_update().get(pk=policy.pk)
    current = period_start()
    existing = BudgetReservation.objects.filter(run=run, reservation_key=key).first()
    if existing:
        return existing
    usage = BudgetReservation.objects.filter(
        workspace=run.workspace, period_start=current,
    ).exclude(status=BudgetReservation.RELEASED).aggregate(
        tokens=Sum(Case(
            When(actual_tokens__isnull=False, then=F("actual_tokens")),
            default=F("estimated_tokens"), output_field=IntegerField(),
        )),
        cost=Sum(Case(
            When(actual_cost_microunits__isnull=False, then=F("actual_cost_microunits")),
            default=F("estimated_cost_microunits"), output_field=IntegerField(),
        ), filter=Q(estimated_cost_microunits__isnull=False) | Q(actual_cost_microunits__isnull=False)),
    )
    run_usage = BudgetReservation.objects.filter(run=run).exclude(status=BudgetReservation.RELEASED).aggregate(
        tokens=Sum(Case(
            When(actual_tokens__isnull=False, then=F("actual_tokens")),
            default=F("estimated_tokens"), output_field=IntegerField(),
        )),
    )["tokens"] or 0
    if run_usage + estimated_tokens > policy.max_run_tokens:
        raise ValidationError("Il limite token della singola esecuzione sarebbe superato.")
    if policy.monthly_token_budget is not None and (usage["tokens"] or 0) + estimated_tokens > policy.monthly_token_budget:
        raise ValidationError("Budget token mensile esaurito.")
    if policy.monthly_budget_microunits is not None:
        if estimated_cost_microunits is None:
            raise ValidationError("Costo non stimabile con un budget monetario rigido.")
        if (usage["cost"] or 0) + estimated_cost_microunits > policy.monthly_budget_microunits:
            raise ValidationError("Budget monetario mensile esaurito.")
    return BudgetReservation.objects.create(
        run=run, workspace=run.workspace, reservation_key=key, period_start=current,
        estimated_tokens=estimated_tokens, estimated_cost_microunits=estimated_cost_microunits,
    )


def reconcile_budget(reservation, *, actual_tokens, actual_cost_microunits):
    reservation.actual_tokens = actual_tokens
    reservation.actual_cost_microunits = actual_cost_microunits
    reservation.status = (
        BudgetReservation.RECONCILED if actual_tokens is not None and actual_cost_microunits is not None
        else BudgetReservation.ESTIMATED
    )
    reservation.save(update_fields=("actual_tokens", "actual_cost_microunits", "status", "updated_at"))


def release_budget(reservation):
    reservation.status = BudgetReservation.RELEASED
    reservation.save(update_fields=("status", "updated_at"))
