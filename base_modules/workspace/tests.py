from io import StringIO

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from base_modules.user_manager.models import ExternalIdentity, User
from plugins.plugin_example.models import ExampleModel

from .models import Workspace, WorkspaceUser


class WorkspaceIsolationTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("person-a", "a@example.test", password="unused")
        self.other = User.objects.create_user("person-b", "b@example.test", password="unused")
        self.own_workspace = Workspace.objects.create(workspace_name="Own")
        self.foreign_workspace = Workspace.objects.create(workspace_name="Foreign")
        WorkspaceUser.objects.create(user=self.user, workspace=self.own_workspace)
        WorkspaceUser.objects.create(user=self.other, workspace=self.foreign_workspace)
        self.own_item = ExampleModel.objects.create(workspace=self.own_workspace, created_by=self.user, name="Own")
        self.foreign_item = ExampleModel.objects.create(workspace=self.foreign_workspace, created_by=self.other, name="Foreign")
        self.client = APIClient()

    def test_scoped_api_requires_authenticated_workspace_selection(self):
        url = "/api/plugin-example/examples/"
        self.assertIn(self.client.get(url).status_code, (401, 403))
        self.client.force_authenticate(user=self.user)
        self.assertEqual(self.client.get(url).status_code, 400)
        self.assertEqual(self.client.get(url, HTTP_X_WORKSPACE_ID=str(self.foreign_workspace.pk)).status_code, 403)

    def test_scoped_api_rejects_out_of_range_workspace_header(self):
        self.client.force_authenticate(user=self.user)
        url = "/api/plugin-example/examples/"
        for value in ("0", "9223372036854775808", "9" * 5000, "1x"):
            with self.subTest(value=value[:24]):
                response = self.client.get(url, HTTP_X_WORKSPACE_ID=value)
                self.assertEqual(response.status_code, 400)
        self.assertEqual(ExampleModel.objects.count(), 2)

    def test_scoped_api_filters_objects_and_related_workspace(self):
        self.client.force_authenticate(user=self.user)
        header = {"HTTP_X_WORKSPACE_ID": str(self.own_workspace.pk)}
        response = self.client.get("/api/plugin-example/examples/", **header)
        self.assertEqual(response.status_code, 200)
        self.assertEqual([item["id"] for item in response.data], [self.own_item.pk])
        self.assertEqual(self.client.get(f"/api/plugin-example/examples/{self.foreign_item.pk}/", **header).status_code, 404)
        created = self.client.post("/api/plugin-example/examples/", {"name": "New", "workspace": self.foreign_workspace.pk}, **header)
        self.assertEqual(created.status_code, 201)
        self.assertEqual(ExampleModel.objects.get(pk=created.data["id"]).workspace, self.own_workspace)

    def test_workspace_directory_does_not_expose_or_allow_editing_foreign_data(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.get("/api/workspace/workspaces/")
        self.assertEqual([item["id"] for item in response.data], [self.own_workspace.pk])
        self.assertEqual(self.client.get(f"/api/workspace/workspaces/{self.foreign_workspace.pk}/").status_code, 404)
        self.assertEqual(self.client.get("/api/workspace/workspace-users/").data[0]["user"]["id"], self.user.pk)
        self.assertEqual(self.client.get("/api/workspace/users/").data[0]["id"], self.user.pk)
        self.assertEqual(self.client.post("/api/workspace/workspaces/", {"workspace_name": "New"}).status_code, 403)
        self.assertEqual(self.client.post("/api/workspace/workspace-users/", {
            "user_id": self.user.pk, "workspace_id": self.foreign_workspace.pk,
        }).status_code, 403)

    def test_session_lists_only_own_memberships(self):
        self.assertIn(self.client.get("/api/workspace/session/").status_code, (401, 403))
        self.client.force_authenticate(user=self.user)
        response = self.client.get("/api/workspace/session/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["user"]["id"], self.user.pk)
        self.assertEqual(response.data["workspaces"], [{
            "id": self.own_workspace.pk, "name": "Own", "role": "member",
        }])


@override_settings(AUTH_MODE="keycloak", KEYCLOAK_ISSUER="https://id.example.test/realms/mixtum")
class WorkspaceOnboardingCommandTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("person-a", "a@example.test")
        self.identity = ExternalIdentity.objects.create(
            user=self.user, issuer="https://id.example.test/realms/mixtum", subject="verified-subject"
        )

    def grant(self, **options):
        return call_command("grant_workspace_member", stdout=StringIO(), **options)

    def test_creates_first_workspace_for_verified_identity_without_global_privileges(self):
        self.grant(subject="verified-subject", new_workspace_name="Cliente Uno")
        workspace = Workspace.objects.get(workspace_name="Cliente Uno")
        membership = WorkspaceUser.objects.get(user=self.user, workspace=workspace)
        self.assertEqual(membership.role, "member")
        self.user.refresh_from_db()
        self.assertFalse(self.user.is_staff)
        self.assertFalse(self.user.is_superuser)
        client = APIClient()
        client.force_authenticate(user=self.user)
        response = client.get("/api/workspace/session/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["workspaces"][0]["id"], workspace.pk)

    def test_refuses_unknown_inactive_or_wrong_issuer_identity(self):
        for subject in ("unknown", " "):
            with self.subTest(subject=subject), self.assertRaises(CommandError):
                self.grant(subject=subject, new_workspace_name="Denied")
        self.identity.issuer = "https://another.example.test/realms/mixtum"
        self.identity.save(update_fields=["issuer"])
        with self.assertRaises(CommandError):
            self.grant(subject="verified-subject", new_workspace_name="Denied")
        self.identity.issuer = "https://id.example.test/realms/mixtum"
        self.identity.save(update_fields=["issuer"])
        self.user.is_active = False
        self.user.save(update_fields=["is_active"])
        with self.assertRaises(CommandError):
            self.grant(subject="verified-subject", new_workspace_name="Denied")
        self.assertFalse(Workspace.objects.exists())

    def test_existing_workspace_requires_explicit_id_and_repeat_does_not_change_role(self):
        workspace = Workspace.objects.create(workspace_name="Existing")
        with self.assertRaises(CommandError):
            self.grant(subject="verified-subject", new_workspace_name="Accidental")
        with self.assertRaises(CommandError):
            self.grant(subject="verified-subject", workspace_id=workspace.pk + 1)
        self.grant(subject="verified-subject", workspace_id=workspace.pk)
        membership = WorkspaceUser.objects.get(user=self.user, workspace=workspace)
        membership.role = "owner"
        membership.save(update_fields=["role"])
        self.grant(subject="verified-subject", workspace_id=workspace.pk)
        self.assertEqual(WorkspaceUser.objects.filter(user=self.user, workspace=workspace).count(), 1)
        membership.refresh_from_db()
        self.assertEqual(membership.role, "owner")

    def test_additional_workspace_requires_explicit_confirmation_and_verified_identity(self):
        first = Workspace.objects.create(workspace_name="Existing")
        with self.assertRaises(CommandError):
            self.grant(subject="verified-subject", new_workspace_name="Second")
        with self.assertRaises(CommandError):
            self.grant(subject="unknown", new_workspace_name="Second", allow_additional_workspace=True)
        with self.assertRaises(CommandError):
            self.grant(subject="verified-subject", workspace_id=first.pk, allow_additional_workspace=True)
        self.assertEqual(list(Workspace.objects.values_list("pk", flat=True)), [first.pk])

        self.grant(subject="verified-subject", new_workspace_name="Second", allow_additional_workspace=True)
        second = Workspace.objects.get(workspace_name="Second")
        self.assertNotEqual(first.pk, second.pk)
        self.assertTrue(WorkspaceUser.objects.filter(user=self.user, workspace=second, role="member").exists())
        self.user.refresh_from_db()
        self.assertFalse(self.user.is_staff)

    @override_settings(AUTH_MODE="django")
    def test_refuses_django_auth_mode(self):
        with self.assertRaises(CommandError):
            self.grant(subject="verified-subject", new_workspace_name="Denied")
        self.assertFalse(Workspace.objects.exists())
