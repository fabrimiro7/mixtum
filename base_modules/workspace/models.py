# workspace/models.py
from django.db import models

from base_modules.user_manager.models import User

class Workspace(models.Model):
    """
    Modello per rappresentare uno spazio di lavoro.
    """
    workspace_name = models.CharField(max_length=255, verbose_name="Nome Workspace")
    workspace_description = models.TextField(blank=True, null=True, verbose_name="Descrizione Workspace")
    workspace_logo = models.FileField(upload_to='workspace_logos/', blank=True, null=True, verbose_name="Logo Workspace")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.workspace_name

    class Meta:
        verbose_name = "Workspace"
        verbose_name_plural = "Workspaces"
        ordering = ['workspace_name']

class WorkspaceUser(models.Model):
    """
    Modello per collegare un Utente a un Workspace.
    Questo modello rappresenta l'appartenenza di un utente a uno specifico workspace.
    """
    MEMBER = "member"
    OWNER = "owner"
    ROLES = ((MEMBER, "Membro"), (OWNER, "Gestore"))

    user = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name="Utente")
    workspace = models.ForeignKey(Workspace, on_delete=models.CASCADE, verbose_name="Workspace")
    role = models.CharField(max_length=50, choices=ROLES, default=MEMBER, verbose_name="Ruolo")
    date_joined = models.DateTimeField(auto_now_add=True, verbose_name="Data di Adesione")

    def __str__(self):
        return f"{self.user.username} in {self.workspace.workspace_name}"

    class Meta:
        verbose_name = "Utente Workspace"
        verbose_name_plural = "Utenti Workspace"
        unique_together = ('user', 'workspace')
        ordering = ['workspace', 'user']


class AdminAuditEvent(models.Model):
    """Persistent, credential-free record of administrative mutations."""

    SUCCESS = "success"
    DENIED = "denied"
    OUTCOMES = ((SUCCESS, "Successo"), (DENIED, "Negato"))

    actor = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, related_name="admin_audit_events",
    )
    workspace = models.ForeignKey(
        Workspace, on_delete=models.SET_NULL, null=True, blank=True, related_name="admin_audit_events",
    )
    target_user = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name="targeted_admin_audit_events",
    )
    action = models.CharField(max_length=80)
    outcome = models.CharField(max_length=16, choices=OUTCOMES)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at", "-id")
        indexes = [models.Index(fields=("workspace", "created_at"), name="admin_audit_workspace_idx")]
