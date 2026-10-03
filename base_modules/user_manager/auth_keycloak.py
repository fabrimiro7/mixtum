from functools import lru_cache

import jwt
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import IntegrityError, transaction
from rest_framework.authentication import BaseAuthentication, get_authorization_header
from rest_framework.exceptions import AuthenticationFailed

from .models import ExternalIdentity, User


@lru_cache(maxsize=4)
def _jwks_client(url):
    return jwt.PyJWKClient(url, timeout=5)


class KeycloakJWTAuthentication(BaseAuthentication):
    """Accept only signed Keycloak access tokens for the configured API audience."""

    def authenticate_header(self, request):
        return "Bearer"

    def authenticate(self, request):
        parts = get_authorization_header(request).split()
        if not parts:
            return None
        if parts[0].lower() != b"bearer":
            return None
        if len(parts) != 2:
            raise AuthenticationFailed("Malformed bearer token")

        issuer = getattr(settings, "KEYCLOAK_ISSUER", "")
        audience = getattr(settings, "KEYCLOAK_API_AUDIENCE", "")
        jwks_url = getattr(settings, "KEYCLOAK_JWKS_URL", "")
        if not all((issuer, audience, jwks_url)):
            raise AuthenticationFailed("Keycloak API authentication is not configured")

        try:
            token = parts[1].decode("ascii")
            signing_key = _jwks_client(jwks_url).get_signing_key_from_jwt(token).key
            payload = jwt.decode(
                token,
                signing_key,
                algorithms=["RS256"],
                issuer=issuer,
                audience=audience,
                options={"require": ["exp", "iat", "iss", "sub", "aud", "typ"]},
            )
        except (UnicodeDecodeError, jwt.PyJWTError, ValueError, OSError):
            raise AuthenticationFailed("Invalid bearer token") from None

        if payload.get("typ") != "Bearer":
            raise AuthenticationFailed("Invalid token type")
        subject = payload.get("sub")
        if not isinstance(subject, str) or not subject or len(subject) > 255:
            raise AuthenticationFailed("Invalid token subject")

        user = self._user_for_identity(issuer, subject, payload)
        if not user.is_active:
            raise AuthenticationFailed("Inactive user")
        return user, payload

    @staticmethod
    def _user_for_identity(issuer, subject, payload):
        identity = ExternalIdentity.objects.select_related("user").filter(issuer=issuer, subject=subject).first()
        if identity:
            return identity.user

        email = payload.get("email")
        if email is not None:
            if not isinstance(email, str) or len(email) > 70:
                raise AuthenticationFailed("Invalid identity profile")
            try:
                validate_email(email)
            except ValidationError:
                raise AuthenticationFailed("Invalid identity profile") from None

        # Existing local accounts require an explicit administrator-approved link.
        if email and User.objects.filter(email__iexact=email).exists():
            raise AuthenticationFailed("Identity requires an explicit account link")

        username = payload.get("preferred_username")
        if not isinstance(username, str) or not username:
            username = subject
        first_name = payload.get("given_name")
        last_name = payload.get("family_name")
        try:
            with transaction.atomic():
                user = User(
                    email=email,
                    username=username[:40],
                    first_name=first_name[:50] if isinstance(first_name, str) else "",
                    last_name=last_name[:50] if isinstance(last_name, str) else "",
                )
                user.set_unusable_password()
                user.save()
                ExternalIdentity.objects.create(user=user, issuer=issuer, subject=subject)
                return user
        except IntegrityError:
            identity = ExternalIdentity.objects.select_related("user").filter(issuer=issuer, subject=subject).first()
            if identity:
                return identity.user
            raise AuthenticationFailed("Identity could not be provisioned") from None
