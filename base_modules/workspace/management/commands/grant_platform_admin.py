from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from base_modules.user_manager.models import ExternalIdentity


class Command(BaseCommand):
    help = "Abilita come amministratore centrale un'identità Keycloak già verificata."

    def add_arguments(self, parser):
        parser.add_argument("--subject", required=True, help="Sub/ID utente Keycloak già autenticato")

    @transaction.atomic
    def handle(self, *args, **options):
        if settings.AUTH_MODE != "keycloak":
            raise CommandError("Il comando richiede AUTH_MODE=keycloak.")
        issuer = getattr(settings, "KEYCLOAK_ISSUER", "")
        subject = options["subject"].strip()
        if not issuer or not subject or len(subject) > 255:
            raise CommandError("Issuer o subject non valido.")

        identity = ExternalIdentity.objects.select_for_update().select_related("user").filter(
            issuer=issuer, subject=subject,
        ).first()
        if identity is None or not identity.user.is_active:
            raise CommandError("Identità non trovata o utente inattivo: eseguire prima un login OIDC valido.")

        user = identity.user
        changed = not user.is_superuser
        if changed:
            user.is_superuser = True
            user.save(update_fields=("is_superuser",))
        state = "abilitato" if changed else "già abilitato"
        self.stdout.write(f"Amministratore centrale {state}: utente {user.pk}.")
