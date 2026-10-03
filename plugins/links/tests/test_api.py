from django.contrib import admin
from django.test import RequestFactory, TestCase
from rest_framework.test import APIClient

from base_modules.user_manager.models import User
from base_modules.workspace.models import Workspace, WorkspaceUser
from plugins.links.models import Link


class LinksWorkspaceApiTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("links-a", "links-a@example.test", password="unused")
        self.other_user = User.objects.create_user("links-b", "links-b@example.test", password="unused")
        self.workspace = Workspace.objects.create(workspace_name="Links A")
        self.other_workspace = Workspace.objects.create(workspace_name="Links B")
        WorkspaceUser.objects.create(user=self.user, workspace=self.workspace)
        WorkspaceUser.objects.create(user=self.other_user, workspace=self.other_workspace)
        self.own_link = Link.objects.create(workspace=self.workspace, title="Own", url="https://example.test/own")
        self.foreign_link = Link.objects.create(
            workspace=self.other_workspace, title="Foreign", url="https://example.test/foreign",
        )
        self.legacy_link = Link.objects.create(title="Legacy", url="https://example.test/legacy")
        self.client = APIClient()
        self.url = "/api/plugin-links/links/"
        self.header = {"HTTP_X_WORKSPACE_ID": str(self.workspace.pk)}

    def test_anonymous_and_missing_or_foreign_workspace_are_rejected(self):
        self.assertIn(self.client.get(self.url, **self.header).status_code, (401, 403))
        self.client.force_authenticate(user=self.user)
        self.assertEqual(self.client.get(self.url).status_code, 400)
        self.assertEqual(self.client.get(self.url, HTTP_X_WORKSPACE_ID=str(self.other_workspace.pk)).status_code, 403)

    def test_list_excludes_foreign_and_unassigned_legacy_rows(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.get(self.url, **self.header)
        self.assertEqual(response.status_code, 200)
        self.assertEqual([link["id"] for link in response.data], [self.own_link.pk])

    def test_create_uses_authorized_workspace_and_ignores_generic_target_input(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.post(self.url, {
            "title": "Created", "url": "https://example.test/new",
            "workspace": self.other_workspace.pk, "content_type_id": 1, "object_id": self.foreign_link.pk,
        }, **self.header)
        self.assertEqual(response.status_code, 201)
        created = Link.objects.get(pk=response.data["id"])
        self.assertEqual(created.workspace, self.workspace)
        self.assertIsNone(created.content_type_id)
        self.assertIsNone(created.object_id)

    def test_invalid_url_is_rejected(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.post(self.url, {"title": "Bad", "url": "javascript:alert(1)"}, **self.header)
        self.assertEqual(response.status_code, 400)

    def test_foreign_or_legacy_object_cannot_be_read_or_mutated(self):
        self.client.force_authenticate(user=self.user)
        for link in (self.foreign_link, self.legacy_link):
            with self.subTest(link=link.pk):
                url = f"{self.url}{link.pk}/"
                self.assertEqual(self.client.get(url, **self.header).status_code, 404)
                self.assertEqual(self.client.patch(url, {"title": "Changed"}, **self.header).status_code, 404)
                self.assertEqual(self.client.delete(url, **self.header).status_code, 404)
                link.refresh_from_db()
                self.assertNotEqual(link.title, "Changed")

    def test_own_link_can_be_updated_and_deleted(self):
        self.client.force_authenticate(user=self.user)
        url = f"{self.url}{self.own_link.pk}/"
        self.assertEqual(self.client.patch(url, {"title": "Updated"}, **self.header).status_code, 200)
        self.own_link.refresh_from_db()
        self.assertEqual(self.own_link.title, "Updated")
        self.assertEqual(self.client.delete(url, **self.header).status_code, 204)
        self.assertFalse(Link.objects.filter(pk=self.own_link.pk).exists())

    def test_legacy_global_route_is_not_exposed(self):
        self.client.force_authenticate(user=self.user)
        self.assertEqual(self.client.get("/api/links/links/", **self.header).status_code, 404)

    def test_legacy_admin_is_superuser_read_only(self):
        link_admin = admin.site._registry[Link]
        request = RequestFactory().get("/admin/links/link/")
        self.user.is_staff = True
        request.user = self.user
        self.assertFalse(link_admin.has_module_permission(request))
        self.assertFalse(link_admin.has_view_permission(request))

        request.user = User.objects.create_superuser("root-links", "root-links@example.test", password="unused")
        self.assertTrue(link_admin.has_view_permission(request))
        self.assertFalse(link_admin.has_add_permission(request))
        self.assertFalse(link_admin.has_change_permission(request))
        self.assertFalse(link_admin.has_delete_permission(request))
