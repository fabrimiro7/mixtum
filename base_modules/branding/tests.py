from django.test import TestCase
from rest_framework.test import APIClient

from base_modules.user_manager.models import User
from base_modules.workspace.models import Workspace, WorkspaceUser

from .models import BrandingSettings


class BrandingIsolationTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("branding-a", "branding-a@example.test", password="unused")
        self.other = User.objects.create_user("branding-b", "branding-b@example.test", password="unused")
        self.own = Workspace.objects.create(workspace_name="Own")
        self.foreign = Workspace.objects.create(workspace_name="Foreign")
        WorkspaceUser.objects.create(user=self.user, workspace=self.own)
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
