from django.test import TestCase
from rest_framework.test import APIClient

from base_modules.user_manager.models import User
from base_modules.workspace.models import Workspace, WorkspaceUser

from .models import Item


class ItemAPITests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("starter", "starter@example.test", password="unused")
        self.own = Workspace.objects.create(workspace_name="Own")
        self.foreign = Workspace.objects.create(workspace_name="Foreign")
        WorkspaceUser.objects.create(user=self.user, workspace=self.own)
        self.foreign_item = Item.objects.create(workspace=self.foreign, created_by=self.user, name="Foreign")
        self.client = APIClient()
        self.url = "/api/starter-plugin/items/"

    def test_access_and_workspace_isolation(self):
        self.assertIn(self.client.get(self.url).status_code, (401, 403))
        self.client.force_authenticate(user=self.user)
        self.assertEqual(self.client.get(self.url).status_code, 400)
        self.assertEqual(self.client.get(self.url, HTTP_X_WORKSPACE_ID=str(self.foreign.pk)).status_code, 403)
        header = {"HTTP_X_WORKSPACE_ID": str(self.own.pk)}
        self.assertEqual(self.client.get(self.url, **header).data, [])
        self.assertEqual(self.client.get(f"{self.url}{self.foreign_item.pk}/", **header).status_code, 404)

    def test_create_ignores_forged_ownership_and_rejects_invalid_name(self):
        self.client.force_authenticate(user=self.user)
        header = {"HTTP_X_WORKSPACE_ID": str(self.own.pk)}
        response = self.client.post(self.url, {
            "name": "Own", "workspace": self.foreign.pk, "created_by": 99999,
        }, **header)
        self.assertEqual(response.status_code, 201)
        item = Item.objects.get(pk=response.data["id"])
        self.assertEqual((item.workspace, item.created_by), (self.own, self.user))
        self.assertEqual(self.client.post(self.url, {"name": ""}, **header).status_code, 400)
        self.assertEqual(self.client.delete(f"{self.url}{item.pk}/", **header).status_code, 405)
