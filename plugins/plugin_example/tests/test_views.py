from django.test import TestCase
from rest_framework.test import APIClient

from base_modules.user_manager.models import User
from base_modules.workspace.models import Workspace, WorkspaceUser
from plugins.plugin_example.models import ExampleModel


class ExampleModelViewTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("example", "example@example.test", password="unused")
        self.other_user = User.objects.create_user("other", "other@example.test", password="unused")
        self.workspace = Workspace.objects.create(workspace_name="Own")
        self.other_workspace = Workspace.objects.create(workspace_name="Other")
        WorkspaceUser.objects.create(user=self.user, workspace=self.workspace)
        WorkspaceUser.objects.create(user=self.other_user, workspace=self.other_workspace)
        self.item = ExampleModel.objects.create(workspace=self.workspace, created_by=self.user, name="Own item")
        self.other_item = ExampleModel.objects.create(
            workspace=self.other_workspace, created_by=self.other_user, name="Other item",
        )
        self.client = APIClient()
        self.url = "/api/plugin-example/examples/"
        self.header = {"HTTP_X_WORKSPACE_ID": str(self.workspace.pk)}

    def test_list_requires_authentication(self):
        self.assertIn(self.client.get(self.url, **self.header).status_code, (401, 403))

    def test_list_requires_valid_workspace_membership(self):
        self.client.force_authenticate(user=self.user)
        self.assertEqual(self.client.get(self.url).status_code, 400)
        self.assertEqual(self.client.get(self.url, HTTP_X_WORKSPACE_ID=str(self.other_workspace.pk)).status_code, 403)

    def test_list_returns_only_selected_workspace(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.get(self.url, **self.header)
        self.assertEqual(response.status_code, 200)
        self.assertEqual([item["id"] for item in response.data], [self.item.pk])

    def test_create_uses_server_workspace_and_actor(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.post(self.url, {
            "name": "New", "workspace": self.other_workspace.pk, "created_by": self.other_user.pk,
        }, **self.header)
        self.assertEqual(response.status_code, 201)
        created = ExampleModel.objects.get(pk=response.data["id"])
        self.assertEqual((created.workspace, created.created_by), (self.workspace, self.user))

    def test_create_returns_400_with_invalid_data(self):
        self.client.force_authenticate(user=self.user)
        self.assertEqual(self.client.post(self.url, {"name": ""}, **self.header).status_code, 400)

    def test_detail_requires_authentication(self):
        self.assertIn(self.client.get(f"{self.url}{self.item.pk}/", **self.header).status_code, (401, 403))

    def test_detail_returns_200(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.get(f"{self.url}{self.item.pk}/", **self.header)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["id"], self.item.pk)

    def test_foreign_detail_and_mutations_are_not_found(self):
        self.client.force_authenticate(user=self.user)
        url = f"{self.url}{self.other_item.pk}/"
        self.assertEqual(self.client.get(url, **self.header).status_code, 404)
        self.assertEqual(self.client.patch(url, {"name": "Changed"}, **self.header).status_code, 404)
        self.assertEqual(self.client.delete(url, **self.header).status_code, 404)
        self.other_item.refresh_from_db()
        self.assertEqual(self.other_item.name, "Other item")

    def test_patch_updates_name_without_changing_workspace(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.patch(f"{self.url}{self.item.pk}/", {
            "name": "Updated", "workspace": self.other_workspace.pk,
        }, **self.header)
        self.assertEqual(response.status_code, 200)
        self.item.refresh_from_db()
        self.assertEqual((self.item.name, self.item.workspace), ("Updated", self.workspace))

    def test_delete_returns_204(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.delete(f"{self.url}{self.item.pk}/", **self.header)
        self.assertEqual(response.status_code, 204)
        self.assertFalse(ExampleModel.objects.filter(pk=self.item.pk).exists())
