from django.http import Http404
from django.test import TestCase

from base_modules.user_manager.models import User
from base_modules.workspace.models import Workspace
from plugins.plugin_example.models import ExampleModel
from plugins.plugin_example.services import ExampleModelService


class ExampleModelServiceTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("example", "example@example.test", password="unused")
        self.workspace = Workspace.objects.create(workspace_name="Example")
        self.other_workspace = Workspace.objects.create(workspace_name="Other")

    def test_create_scopes_to_server_workspace_and_actor(self):
        item = ExampleModelService.create({"name": "Created"}, self.user, self.workspace)
        self.assertEqual((item.workspace, item.created_by, item.name), (self.workspace, self.user, "Created"))
        self.assertEqual(list(ExampleModelService.get_list(self.other_workspace)), [])

    def test_get_by_id_raises_404_if_not_found_or_wrong_workspace(self):
        item = ExampleModel.objects.create(workspace=self.workspace, name="Found")
        self.assertEqual(ExampleModelService.get_by_id(item.pk, self.workspace), item)
        with self.assertRaises(Http404):
            ExampleModelService.get_by_id(item.pk, self.other_workspace)
        with self.assertRaises(Http404):
            ExampleModelService.get_by_id(item.pk + 1, self.workspace)

    def test_update(self):
        item = ExampleModel.objects.create(workspace=self.workspace, name="Before")
        ExampleModelService.update(item, {"name": "After"})
        item.refresh_from_db()
        self.assertEqual(item.name, "After")

    def test_delete(self):
        item = ExampleModel.objects.create(workspace=self.workspace, name="Delete")
        ExampleModelService.delete(item)
        self.assertFalse(ExampleModel.objects.filter(pk=item.pk).exists())
