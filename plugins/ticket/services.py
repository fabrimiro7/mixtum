from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404
from rest_framework.exceptions import PermissionDenied

from .models import AssistanceManager, ClientCompany, CompanyMembership, OperatorGrant, Ticket


def companies_for_requester(*, user, workspace):
    return ClientCompany.objects.filter(workspace=workspace, memberships__user=user).distinct()


def visible_tickets(*, user, workspace):
    """Assignment is deliberately absent: it never grants read access."""
    tickets = Ticket.objects.filter(workspace=workspace).select_related("company")
    if AssistanceManager.objects.filter(workspace=workspace, user=user).exists():
        return tickets

    memberships = CompanyMembership.objects.filter(user=user).values("company_id")
    referent_companies = CompanyMembership.objects.filter(
        user=user, role=CompanyMembership.REFERENT,
    ).values("company_id")
    operator_companies = OperatorGrant.objects.filter(user=user).values("company_id")
    return tickets.filter(
        Q(company_id__in=referent_companies)
        | Q(company_id__in=operator_companies)
        | Q(requester=user, company_id__in=memberships)
    )


@transaction.atomic
def create_ticket(*, user, workspace, company_id, title, description):
    company = get_object_or_404(ClientCompany, pk=company_id, workspace=workspace)
    # Lock the membership until insert so concurrent revocation cannot authorize a new request.
    membership = CompanyMembership.objects.select_for_update().filter(company=company, user=user).first()
    if membership is None:
        raise PermissionDenied("Non sei autorizzato a creare richieste per questa azienda.")
    return Ticket.objects.create(
        workspace=workspace, company=company, requester=user, title=title, description=description,
    )
