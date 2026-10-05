from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from base_modules.user_manager.models import ExternalIdentity
from base_modules.workspace.models import Workspace, WorkspaceUser


class Command(BaseCommand):
    help = "Concede una membership a un'identità Keycloak già verificata da Mixtum."

    def add_arguments(self, parser):
        parser.add_argument("--subject", required=True, help="Sub/ID utente Keycloak già autenticato")
        workspace = parser.add_mutually_exclusive_group(required=True)
        workspace.add_argument("--new-workspace-name", help="Crea un workspace e concede la prima membership")
        workspace.add_argument("--workspace-id", type=int, help="ID di un workspace esistente")
        parser.add_argument(
            "--allow-additional-workspace", action="store_true",
            help="Conferma esplicita per creare un workspace quando ne esiste già uno",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        if settings.AUTH_MODE != "keycloak":
            raise CommandError("Il comando richiede AUTH_MODE=keycloak.")
        issuer = getattr(settings, "KEYCLOAK_ISSUER", "")
        subject = options["subject"].strip()
        if not issuer or not subject or len(subject) > 255:
            raise CommandError("Issuer o subject non valido.")

        identity = ExternalIdentity.objects.select_related("user").filter(
            issuer=issuer, subject=subject
        ).first()
        if identity is None or not identity.user.is_active:
            raise CommandError("Identità non trovata o utente inattivo: eseguire prima un login OIDC valido.")

        name = options["new_workspace_name"]
        if name is None and options["allow_additional_workspace"]:
            raise CommandError("--allow-additional-workspace richiede --new-workspace-name.")
        if name is not None:
            name = name.strip()
            if not name or len(name) > 255:
                raise CommandError("Nome workspace non valido.")
            if Workspace.objects.exists() and not options["allow_additional_workspace"]:
                raise CommandError(
                    "Esiste già un workspace; usare --workspace-id per aggiungere una membership "
                    "oppure --allow-additional-workspace per crearne uno nuovo."
                )
            workspace = Workspace.objects.create(workspace_name=name)
        else:
            workspace_id = options["workspace_id"]
            if workspace_id is None or workspace_id <= 0:
                raise CommandError("ID workspace non valido.")
            workspace = Workspace.objects.filter(pk=workspace_id).first()
            if workspace is None:
                raise CommandError("Workspace non trovato.")

        initial_role = WorkspaceUser.OWNER if name is not None else WorkspaceUser.MEMBER
        membership, created = WorkspaceUser.objects.get_or_create(
            user=identity.user, workspace=workspace, defaults={"role": initial_role}
        )
        state = "creata" if created else "già presente"
        self.stdout.write(f"Membership {state}: utente {identity.user_id}, workspace {workspace.pk}.")
