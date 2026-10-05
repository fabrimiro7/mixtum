from io import BytesIO
import tempfile
from pathlib import Path

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase, TestCase, override_settings
from PIL import Image
from rest_framework.test import APIClient

from base_modules.user_manager.models import ExternalIdentity, User
from base_modules.workspace.models import AdminAuditEvent, Workspace, WorkspaceUser

from .models import BrandingSettings


class BrandingIsolationTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("branding-a", "branding-a@example.test", password="unused")
        self.other = User.objects.create_user("branding-b", "branding-b@example.test", password="unused")
        self.own = Workspace.objects.create(workspace_name="Own")
        self.foreign = Workspace.objects.create(workspace_name="Foreign")
        WorkspaceUser.objects.create(user=self.user, workspace=self.own, role=WorkspaceUser.OWNER)
        WorkspaceUser.objects.create(user=self.other, workspace=self.foreign)
        BrandingSettings.objects.create(workspace=self.foreign, colors={"primary": "#123456"})
        self.client = APIClient()

    def test_workspace_branding_requires_membership(self):
        url = f"/api/branding/workspace/{self.foreign.pk}/"
        self.assertIn(self.client.get(url).status_code, (401, 403))
        self.client.force_authenticate(user=self.user)
        self.assertEqual(self.client.get(url).status_code, 404)
        self.assertEqual(self.client.get(f"/api/branding/workspace/{self.own.pk}/").status_code, 200)

    def test_effective_branding_rejects_foreign_or_anonymous_workspace(self):
        url = f"/api/branding/effective/?workspace_id={self.foreign.pk}"
        self.assertEqual(self.client.get("/api/branding/effective/").status_code, 200)
        self.assertEqual(self.client.get(url).status_code, 403)
        self.client.force_authenticate(user=self.user)
        self.assertEqual(self.client.get(url).status_code, 404)
        self.assertEqual(self.client.get(f"/api/branding/effective/?workspace_id={self.own.pk}").status_code, 200)

    def test_console_theme_uses_global_and_workspace_accent_with_safe_fallback(self):
        global_settings = BrandingSettings.objects.create(colors={"--ed-blue": "#112233"})
        global_theme = self.client.get("/api/branding/effective/").data["theme"]
        self.assertEqual(global_theme, {"primary": "#112233", "on_primary": "#FFFFFF"})

        self.client.force_authenticate(user=self.user)
        workspace_settings = BrandingSettings.objects.create(
            workspace=self.own, colors={"--ed-blue": "#eeeeee"},
        )
        own_url = f"/api/branding/effective/?workspace_id={self.own.pk}"
        self.assertEqual(self.client.get(own_url).data["theme"],
                         {"primary": "#eeeeee", "on_primary": "#000000"})
        workspace_settings.colors = {"--ed-blue": "url(https://attacker.example/x)"}
        workspace_settings.save(update_fields=["colors"])
        self.assertEqual(self.client.get(own_url).data["theme"]["primary"], "#0c0cba")
        global_settings.colors = {"--ed-blue": "not-a-color"}
        global_settings.save(update_fields=["colors"])
        self.assertEqual(self.client.get("/api/branding/effective/").data["theme"]["primary"], "#0c0cba")

    def test_owner_can_update_workspace_but_member_and_foreign_owner_cannot(self):
        member = User.objects.create_user("branding-member", "branding-member@example.test")
        WorkspaceUser.objects.create(user=member, workspace=self.own)
        url = f"/api/branding/workspace/{self.own.pk}/"
        self.client.force_authenticate(user=member)
        self.assertEqual(self.client.patch(url, {"colors": {"--ed-blue": "#123456"}}, format="json").status_code, 403)
        self.client.force_authenticate(user=self.other)
        self.assertEqual(self.client.patch(url, {"colors": {"--ed-blue": "#123456"}}, format="json").status_code, 404)
        self.client.force_authenticate(user=self.user)
        response = self.client.patch(url, {"colors": {"--ed-blue": "#123456"}}, format="json")
        self.assertEqual(response.status_code, 200)
        event = AdminAuditEvent.objects.get(action="branding.workspace.update")
        self.assertEqual((event.actor, event.workspace, event.outcome), (
            self.user, self.own, AdminAuditEvent.SUCCESS,
        ))

    def test_only_superuser_updates_global_branding(self):
        legacy = User.objects.create_user("legacy-branding", "legacy-branding@example.test")
        legacy.is_staff = True
        legacy.permission = 100
        legacy.save(update_fields=("is_staff", "permission"))
        self.client.force_authenticate(user=legacy)
        self.assertEqual(self.client.patch(
            "/api/branding/global/", {"colors": {"--ed-blue": "#123456"}}, format="json",
        ).status_code, 403)

        central = User.objects.create_user("central-branding", "central-branding@example.test")
        central.is_superuser = True
        central.save(update_fields=("is_superuser",))
        ExternalIdentity.objects.create(
            user=central, issuer="https://id.example.test/realms/mixtum", subject="branding-central",
        )
        self.client.force_authenticate(user=central)
        self.assertEqual(self.client.patch(
            "/api/branding/global/", {"colors": {"--ed-blue": "#123456"}}, format="json",
        ).status_code, 200)
        self.assertEqual(AdminAuditEvent.objects.get(action="branding.global.update").actor, central)

    def test_color_and_image_validation_are_explicit(self):
        url = f"/api/branding/workspace/{self.own.pk}/"
        self.client.force_authenticate(user=self.user)
        self.assertEqual(self.client.patch(
            url, {"colors": {"--ed-blue": "url(https://attacker.example/x)"}}, format="json",
        ).status_code, 400)

        image = BytesIO()
        Image.new("RGB", (1, 1), "white").save(image, format="PNG")
        png = image.getvalue()
        gif_image = BytesIO()
        Image.new("RGB", (1, 1), "white").save(gif_image, format="GIF")
        unsupported = SimpleUploadedFile("logo.gif", gif_image.getvalue(), content_type="image/gif")
        self.assertEqual(self.client.patch(url, {"logo_full": unsupported}, format="multipart").status_code, 400)
        oversized = SimpleUploadedFile(
            "logo.png", png + (b"\0" * (2 * 1024 * 1024)), content_type="image/png",
        )
        self.assertEqual(self.client.patch(url, {"logo_full": oversized}, format="multipart").status_code, 400)


class PublicBrandingMediaTests(SimpleTestCase):
    def test_local_branding_file_is_served_when_explicitly_enabled(self):
        with tempfile.TemporaryDirectory() as directory:
            media_root = Path(directory)
            logo = media_root / "branding" / "logos" / "logo.png"
            logo.parent.mkdir(parents=True)
            logo.write_bytes(b"public-branding")

            with override_settings(
                MEDIA_ROOT=media_root,
                SERVE_LOCAL_BRANDING_MEDIA=True,
                USE_S3=False,
            ):
                response = self.client.get("/media/branding/logos/logo.png")

            self.assertEqual(response.status_code, 200)
            self.assertEqual(b"".join(response.streaming_content), b"public-branding")
            self.assertEqual(response.headers["Content-Type"], "image/png")

    @override_settings(SERVE_LOCAL_BRANDING_MEDIA=False, USE_S3=False)
    def test_local_branding_route_is_closed_by_default(self):
        self.assertEqual(self.client.get("/media/branding/logos/logo.png").status_code, 404)

    @override_settings(SERVE_LOCAL_BRANDING_MEDIA=True, USE_S3=True)
    def test_local_branding_route_is_closed_for_s3_storage(self):
        self.assertEqual(self.client.get("/media/branding/logos/logo.png").status_code, 404)

    @override_settings(SERVE_LOCAL_BRANDING_MEDIA=True, USE_S3=False)
    def test_non_branding_media_is_not_routed(self):
        self.assertEqual(self.client.get("/media/attachments/private.txt").status_code, 404)
