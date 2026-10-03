from django.test import TestCase
from rest_framework.test import APIClient

from base_modules.user_manager.models import User
from base_modules.workspace.models import Workspace, WorkspaceUser


class ExternalProbeTests(TestCase):
    def test_api_requires_membership_in_selected_workspace(self):
        user = User.objects.create_user("probe", "probe@example.test", password="unused")
        own = Workspace.objects.create(workspace_name="Own")
        foreign = Workspace.objects.create(workspace_name="Foreign")
        WorkspaceUser.objects.create(user=user, workspace=own)
        client = APIClient()
        url = "/api/external-probe/status/"

        self.assertIn(client.get(url).status_code, (401, 403))
        client.force_authenticate(user=user)
        self.assertEqual(client.get(url).status_code, 400)
        self.assertEqual(client.get(url, HTTP_X_WORKSPACE_ID=str(foreign.pk)).status_code, 403)
        response = client.get(url, HTTP_X_WORKSPACE_ID=str(own.pk))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, {"workspace_id": own.pk, "plugin": "external_probe"})
        self.assertEqual(client.post(url, HTTP_X_WORKSPACE_ID=str(own.pk)).status_code, 405)
