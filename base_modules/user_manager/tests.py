"""OIDC authentication regressions."""

from datetime import timedelta
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import os
import subprocess
import sys
from threading import Thread
from types import SimpleNamespace
from unittest.mock import patch

import jwt
from cryptography.hazmat.primitives.asymmetric import rsa
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.test import APIRequestFactory

from .auth_keycloak import KeycloakJWTAuthentication
from .models import ExternalIdentity, User


@override_settings(
    KEYCLOAK_ISSUER="https://id.example.test/realms/mixtum",
    KEYCLOAK_API_AUDIENCE="mixtum-api",
    KEYCLOAK_JWKS_URL="https://id.example.test/certs",
)
class KeycloakAuthenticationTests(TestCase):
    def setUp(self):
        self.key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        self.authenticator = KeycloakJWTAuthentication()
        patcher = patch("base_modules.user_manager.auth_keycloak._jwks_client")
        self.client_mock = patcher.start()
        self.addCleanup(patcher.stop)
        self.client_mock.return_value.get_signing_key_from_jwt.return_value = SimpleNamespace(key=self.key.public_key())

    def token(self, **changes):
        now = timezone.now()
        claims = {
            "iss": "https://id.example.test/realms/mixtum",
            "sub": "subject-1234",
            "aud": "mixtum-api",
            "iat": now,
            "exp": now + timedelta(minutes=5),
            "typ": "Bearer",
            "email": "new@example.test",
            "realm_access": {"roles": ["superadmin"]},
        }
        claims.update(changes)
        return jwt.encode(claims, self.key, algorithm="RS256")

    def authenticate(self, token):
        request = APIRequestFactory().get("/", HTTP_AUTHORIZATION=f"Bearer {token}")
        return self.authenticator.authenticate(request)[0]

    def test_provisions_by_issuer_subject_without_role_escalation(self):
        user = self.authenticate(self.token())
        self.assertEqual(ExternalIdentity.objects.get(user=user).subject, "subject-1234")
        self.assertFalse(user.is_superuser)
        self.assertFalse(user.is_staff)
        self.assertNotEqual(user.permission, 100)
        self.assertFalse(user.has_usable_password())
        self.assertEqual(self.authenticate(self.token(email="changed@example.test")).pk, user.pk)

    def test_rejects_invalid_signature_issuer_audience_expiry_and_type(self):
        another_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        invalid = [
            jwt.encode({"iss": "https://id.example.test/realms/mixtum", "sub": "subject-1234", "aud": "mixtum-api", "iat": timezone.now(), "exp": timezone.now() + timedelta(minutes=5), "typ": "Bearer"}, another_key, algorithm="RS256"),
            self.token(iss="https://wrong.example.test/realms/mixtum"),
            self.token(aud="other-api"),
            self.token(exp=timezone.now() - timedelta(seconds=1)),
            self.token(typ="ID"),
            self.token(sub=""),
        ]
        for token in invalid:
            with self.subTest(token=token[:12]), self.assertRaises(AuthenticationFailed):
                self.authenticate(token)
        self.assertFalse(ExternalIdentity.objects.exists())

    def test_email_collision_requires_explicit_link(self):
        legacy = User.objects.create_user("legacy", "new@example.test", password="unused")
        with self.assertRaises(AuthenticationFailed):
            self.authenticate(self.token())
        self.assertFalse(ExternalIdentity.objects.exists())
        ExternalIdentity.objects.create(user=legacy, issuer="https://id.example.test/realms/mixtum", subject="subject-1234")
        self.assertEqual(self.authenticate(self.token()).pk, legacy.pk)

    def test_keycloak_mode_does_not_route_legacy_token_apis(self):
        env = os.environ.copy()
        env.update(DJANGO_SETTINGS_MODULE="mixtum_core.settings", AUTH_MODE="keycloak", KEYCLOAK_API_AUDIENCE="mixtum-api")
        code = """
import django
django.setup()
from django.urls import Resolver404, resolve
for path in (
    '/admin/', '/admin/login/',
    '/api/v1/accounts/auth/login/', '/api/v1/users/login/',
    '/api/attachments/list/', '/api/links/links/', '/api/whatsapp/conversations/',
):
    try:
        resolve(path)
    except Resolver404:
        continue
    raise AssertionError(f'Legacy endpoint remains exposed: {path}')
resolve('/api/workspace/session/')
resolve('/api/plugin-links/links/')
from django.test import Client
assert Client().get('/admin/').status_code == 404
"""
        result = subprocess.run([sys.executable, "-c", code], env=env, capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_django_mode_keeps_its_legacy_admin_route(self):
        env = os.environ.copy()
        env.update(DJANGO_SETTINGS_MODULE="mixtum_core.settings", AUTH_MODE="django")
        code = ("import django; django.setup(); from django.urls import resolve; "
                "from django.test import Client; resolve('/admin/login/'); "
                "assert Client().get('/admin/').status_code == 302")
        result = subprocess.run([sys.executable, "-c", code], env=env, capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stderr)


class KeycloakJWKSIntegrationTests(TestCase):
    def test_fetches_jwks_and_validates_signed_access_token(self):
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        jwk = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(key.public_key()))
        jwk.update(kid="test-key", use="sig", alg="RS256")

        class JWKSHandler(BaseHTTPRequestHandler):
            def do_GET(self):
                body = json.dumps({"keys": [jwk]}).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, format, *args):
                pass

        server = HTTPServer(("127.0.0.1", 0), JWKSHandler)
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(thread.join, 2)
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)

        issuer = "https://id.example.test/realms/mixtum"
        now = timezone.now()
        claims = {
            "iss": issuer, "sub": "jwks-subject", "aud": "mixtum-api", "typ": "Bearer",
            "iat": now, "exp": now + timedelta(minutes=5), "email": "jwks@example.test",
        }
        token = jwt.encode(claims, key, algorithm="RS256", headers={"kid": "test-key"})
        request = APIRequestFactory().get("/", HTTP_AUTHORIZATION=f"Bearer {token}")
        with override_settings(
            KEYCLOAK_ISSUER=issuer,
            KEYCLOAK_API_AUDIENCE="mixtum-api",
            KEYCLOAK_JWKS_URL=f"http://127.0.0.1:{server.server_port}/certs",
        ):
            user, _ = KeycloakJWTAuthentication().authenticate(request)
            self.assertEqual(ExternalIdentity.objects.get(user=user).subject, "jwks-subject")
            self.assertFalse(user.is_superuser)
            wrong_audience = jwt.encode({**claims, "aud": "other-api"}, key, algorithm="RS256", headers={"kid": "test-key"})
            invalid = APIRequestFactory().get("/", HTTP_AUTHORIZATION=f"Bearer {wrong_audience}")
            with self.assertRaises(AuthenticationFailed):
                KeycloakJWTAuthentication().authenticate(invalid)
