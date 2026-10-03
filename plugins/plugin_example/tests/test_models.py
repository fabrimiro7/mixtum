from django.test import TestCase

from base_modules.workspace.models import Workspace
from plugins.plugin_example.models import ExampleModel


class ExampleModelTest(TestCase):
    def setUp(self):
        self.workspace = Workspace.objects.create(workspace_name="Example")

    def test_str(self):
        item = ExampleModel.objects.create(workspace=self.workspace, name="Test item")
        self.assertEqual(str(item), "Test item")

    def test_created_at_auto_set(self):
        item = ExampleModel.objects.create(workspace=self.workspace, name="Test item")
        self.assertIsNotNone(item.created_at)
        self.assertIsNotNone(item.updated_at)
