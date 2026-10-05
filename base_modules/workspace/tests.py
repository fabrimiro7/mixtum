from io import StringIO

from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from base_modules.user_manager.models import ExternalIdentity, User
from plugins.plugin_example.models import ExampleModel

from .models import AdminAuditEvent, Workspace, WorkspaceUser


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
            "id": self.own_workspace.pk, "name": "Own", "role": "member", "can_manage": False,
        }])
        self.assertEqual(response.data["capabilities"], {
            "platform_admin": False,
            "manage_global_branding": False,
            "managed_workspace_ids": [],
        })


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
        self.assertEqual(membership.role, "owner")
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
        self.assertTrue(WorkspaceUser.objects.filter(user=self.user, workspace=second, role="owner").exists())
        self.user.refresh_from_db()
        self.assertFalse(self.user.is_staff)

    @override_settings(AUTH_MODE="django")
    def test_refuses_django_auth_mode(self):
        with self.assertRaises(CommandError):
            self.grant(subject="verified-subject", new_workspace_name="Denied")
        self.assertFalse(Workspace.objects.exists())


class WorkspaceAdministrationTests(TestCase):
    def setUp(self):
        self.central = self.verified_user("central")
        self.central.is_superuser = True
        self.central.save(update_fields=("is_superuser",))
        self.owner = self.verified_user("owner")
        self.member = self.verified_user("member")
        self.foreign_owner = self.verified_user("foreign-owner")
        self.unverified = User.objects.create_user("unverified", "unverified@example.test")
        self.workspace = Workspace.objects.create(workspace_name="Managed")
        self.foreign = Workspace.objects.create(workspace_name="Foreign")
        self.owner_membership = WorkspaceUser.objects.create(
            user=self.owner, workspace=self.workspace, role=WorkspaceUser.OWNER,
        )
        self.member_membership = WorkspaceUser.objects.create(
            user=self.member, workspace=self.workspace, role=WorkspaceUser.MEMBER,
        )
        WorkspaceUser.objects.create(
            user=self.foreign_owner, workspace=self.foreign, role=WorkspaceUser.OWNER,
        )
        self.client = APIClient()

    @staticmethod
    def verified_user(name):
        user = User.objects.create_user(name, f"{name}@example.test")
        ExternalIdentity.objects.create(
            user=user, issuer="https://id.example.test/realms/mixtum", subject=f"subject-{name}",
        )
        return user

    def as_user(self, user):
        self.client.force_authenticate(user=user)

    def test_session_exposes_only_backend_derived_capabilities(self):
        self.as_user(self.owner)
        response = self.client.get("/api/workspace/session/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["capabilities"]["managed_workspace_ids"], [self.workspace.pk])
        self.assertFalse(response.data["capabilities"]["platform_admin"])
        self.assertTrue(response.data["workspaces"][0]["can_manage"])

        self.as_user(self.central)
        response = self.client.get("/api/workspace/session/")
        self.assertTrue(response.data["capabilities"]["platform_admin"])
        self.assertTrue(response.data["capabilities"]["manage_global_branding"])

    def test_is_staff_or_legacy_permission_does_not_grant_central_authority(self):
        legacy = self.verified_user("legacy")
        legacy.is_staff = True
        legacy.permission = 100
        legacy.save(update_fields=("is_staff", "permission"))
        self.as_user(legacy)
        self.assertEqual(self.client.get("/api/workspace/workspaces/").data, [])
        response = self.client.post("/api/workspace/workspaces/", {
            "workspace_name": "Denied", "owner_user_id": self.owner.pk,
        })
        self.assertEqual(response.status_code, 403)
        self.assertFalse(Workspace.objects.filter(workspace_name="Denied").exists())

    def test_central_admin_creates_workspace_and_initial_owner_atomically(self):
        self.as_user(self.central)
        response = self.client.post("/api/workspace/workspaces/", {
            "workspace_name": "Created", "workspace_description": "Description",
            "owner_user_id": self.member.pk,
        })
        self.assertEqual(response.status_code, 201)
        created = Workspace.objects.get(pk=response.data["id"])
        self.assertTrue(WorkspaceUser.objects.filter(
            workspace=created, user=self.member, role=WorkspaceUser.OWNER,
        ).exists())
        event = AdminAuditEvent.objects.get(action="workspace.create")
        self.assertEqual((event.actor, event.workspace, event.target_user, event.outcome), (
            self.central, created, self.member, AdminAuditEvent.SUCCESS,
        ))

        denied = self.client.post("/api/workspace/workspaces/", {
            "workspace_name": "No owner", "owner_user_id": self.unverified.pk,
        })
        self.assertEqual(denied.status_code, 400)
        self.assertFalse(Workspace.objects.filter(workspace_name="No owner").exists())

    def test_owner_updates_only_own_workspace_and_member_cannot(self):
        url = f"/api/workspace/workspaces/{self.workspace.pk}/"
        self.as_user(self.member)
        self.assertEqual(self.client.patch(url, {"workspace_description": "Denied"}).status_code, 403)
        self.as_user(self.owner)
        self.assertEqual(self.client.patch(url, {"workspace_description": "Allowed"}).status_code, 200)
        self.assertEqual(self.workspace.admin_audit_events.get().action, "workspace.update")
        foreign_url = f"/api/workspace/workspaces/{self.foreign.pk}/"
        self.assertEqual(self.client.patch(foreign_url, {"workspace_description": "Denied"}).status_code, 404)

        protected_upload = SimpleUploadedFile(
            "workspace.svg", b"<svg onload=alert(1)></svg>", content_type="image/svg+xml",
        )
        self.assertEqual(self.client.patch(
            url, {"workspace_logo": protected_upload}, format="multipart",
        ).status_code, 400)

    def test_owner_sees_assigned_members_but_cannot_assign_from_global_directory(self):
        self.as_user(self.owner)
        memberships = self.client.get("/api/workspace/workspace-users/").data
        self.assertEqual({item["user"]["id"] for item in memberships}, {self.owner.pk, self.member.pk})
        self.assertEqual(self.client.get("/api/workspace/users/").data, [{
            "id": self.owner.pk, "username": self.owner.username, "email": self.owner.email,
        }])
        self.assertEqual(self.client.post("/api/workspace/workspace-users/", {
            "user_id": self.foreign_owner.pk, "workspace_id": self.workspace.pk, "role": "member",
        }).status_code, 403)

        self.as_user(self.central)
        directory_ids = {item["id"] for item in self.client.get("/api/workspace/users/").data}
        self.assertIn(self.foreign_owner.pk, directory_ids)
        self.assertNotIn(self.unverified.pk, directory_ids)
        response = self.client.post("/api/workspace/workspace-users/", {
            "user_id": self.foreign_owner.pk, "workspace_id": self.workspace.pk, "role": "member",
        })
        self.assertEqual(response.status_code, 201)

    def test_last_owner_cannot_be_demoted_or_removed_and_fields_are_protected(self):
        url = f"/api/workspace/workspace-users/{self.owner_membership.pk}/"
        self.as_user(self.owner)
        self.assertEqual(self.client.patch(url, {"role": "member"}).status_code, 400)
        self.assertEqual(self.client.delete(url).status_code, 400)
        self.assertEqual(AdminAuditEvent.objects.filter(
            workspace=self.workspace, outcome=AdminAuditEvent.DENIED,
        ).count(), 2)
        protected = self.client.patch(url, {
            "user_id": self.member.pk, "workspace_id": self.foreign.pk, "role": "owner",
        })
        self.assertEqual(protected.status_code, 400)
        self.owner_membership.refresh_from_db()
        self.assertEqual((self.owner_membership.user, self.owner_membership.workspace, self.owner_membership.role), (
            self.owner, self.workspace, WorkspaceUser.OWNER,
        ))

        second_owner = self.member_membership
        second_owner.role = WorkspaceUser.OWNER
        second_owner.save(update_fields=("role",))
        self.assertEqual(self.client.patch(url, {"role": "member"}).status_code, 200)
        self.owner_membership.refresh_from_db()
        self.assertEqual(self.owner_membership.role, WorkspaceUser.MEMBER)
        self.assertEqual(self.client.delete(
            f"/api/workspace/workspace-users/{second_owner.pk}/"
        ).status_code, 404)

    def test_unknown_legacy_role_never_grants_management(self):
        legacy = self.verified_user("unknown-role")
        membership = WorkspaceUser.objects.create(user=legacy, workspace=self.workspace, role="administrator")
        self.as_user(legacy)
        self.assertEqual(self.client.patch(
            f"/api/workspace/workspaces/{self.workspace.pk}/", {"workspace_description": "Denied"},
        ).status_code, 403)
        self.assertEqual(self.client.patch(
            f"/api/workspace/workspace-users/{membership.pk}/", {"role": "owner"},
        ).status_code, 403)

    def test_revocation_is_immediate(self):
        self.as_user(self.owner)
        response = self.client.delete(f"/api/workspace/workspace-users/{self.member_membership.pk}/")
        self.assertEqual(response.status_code, 204)
        self.as_user(self.member)
        self.assertEqual(self.client.get("/api/workspace/session/").data["workspaces"], [])


@override_settings(AUTH_MODE="keycloak", KEYCLOAK_ISSUER="https://id.example.test/realms/mixtum")
class PlatformAdminCommandTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("central", "central@example.test")
        ExternalIdentity.objects.create(
            user=self.user, issuer="https://id.example.test/realms/mixtum", subject="central-subject",
        )

    def test_grants_only_superuser_to_verified_identity_and_is_idempotent(self):
        for _iteration in range(2):
            call_command("grant_platform_admin", subject="central-subject", stdout=StringIO())
        self.user.refresh_from_db()
        self.assertTrue(self.user.is_superuser)
        self.assertFalse(self.user.is_staff)
        self.assertFalse(self.user.has_usable_password())

    def test_refuses_unknown_subject_or_django_auth_mode(self):
        with self.assertRaises(CommandError):
            call_command("grant_platform_admin", subject="unknown", stdout=StringIO())
        with override_settings(AUTH_MODE="django"), self.assertRaises(CommandError):
            call_command("grant_platform_admin", subject="central-subject", stdout=StringIO())
        self.user.refresh_from_db()
        self.assertFalse(self.user.is_superuser)
