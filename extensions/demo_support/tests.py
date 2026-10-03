from django.test import TestCase
from rest_framework.test import APIClient

from base_modules.user_manager.models import User
from base_modules.workspace.models import Workspace, WorkspaceUser
from plugins.ticket.models import ClientCompany, CompanyMembership, Ticket


class DemoSupportSummaryTests(TestCase):
    def setUp(self):
        self.workspace = Workspace.objects.create(workspace_name="Summary A")
        self.other_workspace = Workspace.objects.create(workspace_name="Summary B")
        self.user = User.objects.create_user("summary-user", "summary@example.test", password="unused")
        self.other = User.objects.create_user("summary-other", "other@example.test", password="unused")
        WorkspaceUser.objects.create(user=self.user, workspace=self.workspace)
        WorkspaceUser.objects.create(user=self.other, workspace=self.other_workspace)
        company = ClientCompany.objects.create(workspace=self.workspace, name="A")
        foreign_company = ClientCompany.objects.create(workspace=self.other_workspace, name="B")
        CompanyMembership.objects.create(company=company, user=self.user)
        CompanyMembership.objects.create(company=foreign_company, user=self.other)
        Ticket.objects.create(workspace=self.workspace, company=company, requester=self.user,
                              title="Visible", description="One")
        Ticket.objects.create(workspace=self.workspace, company=company, requester=self.other,
                              title="Hidden", description="Two", status=Ticket.CLOSED)
        Ticket.objects.create(workspace=self.other_workspace, company=foreign_company, requester=self.other,
                              title="Foreign", description="Three")
        self.client = APIClient()
        self.url = "/api/demo-support/summary/"
        self.header = {"HTTP_X_WORKSPACE_ID": str(self.workspace.pk)}

    def test_authentication_and_workspace_are_required(self):
        self.assertIn(self.client.get(self.url, **self.header).status_code, (401, 403))
        self.client.force_authenticate(user=self.user)
        self.assertEqual(self.client.get(self.url).status_code, 400)
        self.assertEqual(self.client.get(self.url, HTTP_X_WORKSPACE_ID=str(self.other_workspace.pk)).status_code, 403)

    def test_summary_aggregates_only_visible_tickets(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.get(self.url, **self.header)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, {"open": 1, "closed": 0})
        CompanyMembership.objects.get(user=self.user).delete()
        self.assertEqual(self.client.get(self.url, **self.header).data, {"open": 0, "closed": 0})
