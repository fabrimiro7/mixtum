from django.core.exceptions import ValidationError
from django.db import transaction

from base_modules.user_manager.models import User

from .models import AdminAuditEvent, Workspace, WorkspaceUser


def is_workspace_owner(*, user, workspace_id):
    return bool(
        user
        and user.is_authenticated
        and WorkspaceUser.objects.filter(
            user=user, workspace_id=workspace_id, role=WorkspaceUser.OWNER,
        ).exists()
    )


def can_manage_workspace(*, user, workspace_id):
    return bool(user and user.is_authenticated and (
        user.is_superuser or is_workspace_owner(user=user, workspace_id=workspace_id)
    ))


def verified_active_user(user_id):
    user = User.objects.filter(pk=user_id, is_active=True, external_identity__isnull=False).first()
    if user is None:
        raise ValidationError("L'utente deve avere un'identità OIDC verificata ed essere attivo.")
    return user


@transaction.atomic
def create_workspace_with_owner(*, owner, **workspace_data):
    owner = verified_active_user(owner.pk)
    workspace = Workspace.objects.create(**workspace_data)
    WorkspaceUser.objects.create(user=owner, workspace=workspace, role=WorkspaceUser.OWNER)
    return workspace


@transaction.atomic
def create_membership(*, user, workspace, role):
    user = verified_active_user(user.pk)
    Workspace.objects.select_for_update().get(pk=workspace.pk)
    return WorkspaceUser.objects.create(user=user, workspace=workspace, role=role)


@transaction.atomic
def change_membership_role(*, membership, role):
    Workspace.objects.select_for_update().get(pk=membership.workspace_id)
    locked = WorkspaceUser.objects.select_for_update().get(pk=membership.pk)
    if locked.role == WorkspaceUser.OWNER and role != WorkspaceUser.OWNER:
        owners = WorkspaceUser.objects.filter(
            workspace_id=locked.workspace_id, role=WorkspaceUser.OWNER,
        ).count()
        if owners <= 1:
            raise ValidationError("L'ultimo gestore del workspace non può essere declassato.")
    locked.role = role
    locked.save(update_fields=("role",))
    return locked


@transaction.atomic
def delete_membership(*, membership):
    Workspace.objects.select_for_update().get(pk=membership.workspace_id)
    locked = WorkspaceUser.objects.select_for_update().get(pk=membership.pk)
    if locked.role == WorkspaceUser.OWNER:
        owners = WorkspaceUser.objects.filter(
            workspace_id=locked.workspace_id, role=WorkspaceUser.OWNER,
        ).count()
        if owners <= 1:
            raise ValidationError("L'ultimo gestore del workspace non può essere rimosso.")
    workspace_id = locked.workspace_id
    target_user_id = locked.user_id
    locked.delete()
    return workspace_id, target_user_id


def record_admin_event(*, actor, action, outcome, workspace=None, target_user=None):
    return AdminAuditEvent.objects.create(
        actor=actor,
        workspace=workspace,
        target_user=target_user,
        action=action,
        outcome=outcome,
    )
