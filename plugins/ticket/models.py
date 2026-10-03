from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


class ClientCompany(models.Model):
    workspace = models.ForeignKey("workspace.Workspace", on_delete=models.CASCADE, related_name="ticket_companies")
    name = models.CharField(max_length=255)

    class Meta:
        ordering = ("name", "id")
        constraints = [models.UniqueConstraint(fields=("workspace", "name"), name="ticket_company_workspace_name_uniq")]

    def __str__(self):
        return self.name


class CompanyMembership(models.Model):
    REQUESTER = "requester"
    REFERENT = "referent"
    ROLES = ((REQUESTER, "Richiedente"), (REFERENT, "Referente"))

    company = models.ForeignKey(ClientCompany, on_delete=models.CASCADE, related_name="memberships")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="ticket_company_memberships")
    role = models.CharField(max_length=12, choices=ROLES, default=REQUESTER)

    class Meta:
        constraints = [models.UniqueConstraint(fields=("company", "user"), name="ticket_company_member_uniq")]


class OperatorGrant(models.Model):
    company = models.ForeignKey(ClientCompany, on_delete=models.CASCADE, related_name="operator_grants")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="ticket_operator_grants")

    class Meta:
        constraints = [models.UniqueConstraint(fields=("company", "user"), name="ticket_operator_company_uniq")]


class AssistanceManager(models.Model):
    workspace = models.ForeignKey("workspace.Workspace", on_delete=models.CASCADE, related_name="ticket_managers")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="ticket_manager_scopes")

    class Meta:
        constraints = [models.UniqueConstraint(fields=("workspace", "user"), name="ticket_manager_workspace_uniq")]


class Ticket(models.Model):
    OPEN = "open"
    CLOSED = "closed"
    STATUSES = ((OPEN, "Aperto"), (CLOSED, "Chiuso"))

    workspace = models.ForeignKey("workspace.Workspace", on_delete=models.PROTECT, related_name="tickets")
    company = models.ForeignKey(ClientCompany, on_delete=models.PROTECT, related_name="tickets")
    requester = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="requested_tickets")
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="assigned_tickets",
    )
    title = models.CharField(max_length=255)
    description = models.TextField()
    status = models.CharField(max_length=12, choices=STATUSES, default=OPEN)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-created_at", "-id")
        indexes = [models.Index(fields=("workspace", "created_at"), name="ticket_scope_created_idx")]

    def clean(self):
        if self.company_id and self.workspace_id and self.company.workspace_id != self.workspace_id:
            raise ValidationError({"company": "L'azienda deve appartenere al workspace del ticket."})

    def __str__(self):
        return self.title
