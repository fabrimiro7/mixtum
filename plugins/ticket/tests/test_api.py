from django.contrib import admin
from django.core.exceptions import ValidationError
from django.test import RequestFactory, TestCase
from rest_framework.test import APIClient

from base_modules.user_manager.models import User
from base_modules.workspace.models import Workspace, WorkspaceUser
from plugins.ticket.models import AssistanceManager, ClientCompany, CompanyMembership, OperatorGrant, Ticket


class TicketApiTests(TestCase):
    def setUp(self):
        self.workspace = Workspace.objects.create(workspace_name="Support")
        self.other_workspace = Workspace.objects.create(workspace_name="Other")
        self.a = ClientCompany.objects.create(workspace=self.workspace, name="A")
        self.b = ClientCompany.objects.create(workspace=self.workspace, name="B")
        self.foreign = ClientCompany.objects.create(workspace=self.other_workspace, name="Foreign")
        self.requester = self.user("requester")
        self.colleague = self.user("colleague")
        self.referent = self.user("referent")
        self.operator = self.user("operator")
        self.manager = self.user("manager")
        self.outsider = self.user("outsider")
        self.foreign_user = self.user("foreign-user", self.other_workspace)
        for user in (self.requester, self.colleague, self.referent):
            CompanyMembership.objects.create(
                company=self.a, user=user,
                role=CompanyMembership.REFERENT if user == self.referent else CompanyMembership.REQUESTER,
            )
        CompanyMembership.objects.create(company=self.b, user=self.colleague)
        CompanyMembership.objects.create(company=self.foreign, user=self.foreign_user)
        OperatorGrant.objects.create(company=self.a, user=self.operator)
        AssistanceManager.objects.create(workspace=self.workspace, user=self.manager)
        self.own = self.ticket(self.a, self.requester, "Own")
        self.colleague_ticket = self.ticket(self.a, self.colleague, "Colleague")
        self.b_ticket = self.ticket(self.b, self.colleague, "Company B")
        self.foreign_ticket = self.ticket(self.foreign, self.foreign_user, "Foreign")
        self.client = APIClient()
        self.url = "/api/plugin-ticket/tickets/"
        self.header = {"HTTP_X_WORKSPACE_ID": str(self.workspace.pk)}

    def user(self, name, workspace=None):
        user = User.objects.create_user(name, f"{name}@example.test", password="unused")
        WorkspaceUser.objects.create(user=user, workspace=workspace or self.workspace)
        return user

    def ticket(self, company, requester, title):
        return Ticket.objects.create(workspace=company.workspace, company=company, requester=requester,
                                     title=title, description="Description")

    def as_user(self, user):
        self.client.force_authenticate(user=user)

    def ids(self):
        response = self.client.get(self.url, **self.header)
        self.assertEqual(response.status_code, 200)
        return {row["id"] for row in response.data["results"]}

    def test_authentication_and_workspace_are_required(self):
        self.assertIn(self.client.get(self.url, **self.header).status_code, (401, 403))
        self.as_user(self.requester)
        self.assertEqual(self.client.get(self.url).status_code, 400)
        self.assertEqual(self.client.get(self.url, HTTP_X_WORKSPACE_ID=str(self.other_workspace.pk)).status_code, 403)

    def test_visibility_is_role_and_company_scoped(self):
        for user, expected in (
            (self.requester, {self.own.pk}),
            (self.colleague, {self.colleague_ticket.pk, self.b_ticket.pk}),
            (self.referent, {self.own.pk, self.colleague_ticket.pk}),
            (self.operator, {self.own.pk, self.colleague_ticket.pk}),
            (self.manager, {self.own.pk, self.colleague_ticket.pk, self.b_ticket.pk}),
            (self.outsider, set()),
        ):
            with self.subTest(user=user.username):
                self.as_user(user)
                self.assertEqual(self.ids(), expected)
                for ticket in (self.own, self.colleague_ticket, self.b_ticket, self.foreign_ticket):
                    status = self.client.get(f"{self.url}{ticket.pk}/", **self.header).status_code
                    self.assertEqual(status, 200 if ticket.pk in expected else 404)

    def test_assignment_does_not_grant_access(self):
        self.own.assigned_to = self.outsider
        self.own.save(update_fields=("assigned_to",))
        self.as_user(self.outsider)
        self.assertEqual(self.ids(), set())
        self.assertEqual(self.client.get(f"{self.url}{self.own.pk}/", **self.header).status_code, 404)

    def test_revoking_membership_revokes_existing_requester_access(self):
        CompanyMembership.objects.get(company=self.a, user=self.requester).delete()
        self.as_user(self.requester)
        self.assertEqual(self.ids(), set())
        self.assertEqual(self.client.get(f"{self.url}{self.own.pk}/", **self.header).status_code, 404)

    def test_create_uses_server_identity_and_rejects_other_companies(self):
        self.as_user(self.requester)
        payload = {"company_id": self.a.pk, "title": "New", "description": "Help",
                   "workspace": self.other_workspace.pk, "requester": self.outsider.pk,
                   "assigned_to": self.outsider.pk, "status": Ticket.CLOSED}
        response = self.client.post(self.url, payload, **self.header)
        self.assertEqual(response.status_code, 201)
        ticket = Ticket.objects.get(pk=response.data["id"])
        self.assertEqual((ticket.workspace_id, ticket.requester_id, ticket.status),
                         (self.workspace.pk, self.requester.pk, Ticket.OPEN))
        self.assertIsNone(ticket.assigned_to_id)
        self.assertEqual(self.client.post(self.url, {**payload, "company_id": self.b.pk}, **self.header).status_code, 403)
        self.assertEqual(self.client.post(self.url, {**payload, "company_id": self.foreign.pk}, **self.header).status_code, 404)
        self.as_user(self.operator)
        self.assertEqual(self.client.post(self.url, payload, **self.header).status_code, 403)
        self.as_user(self.referent)
        self.assertEqual(self.client.post(self.url, payload, **self.header).status_code, 201)

    def test_company_choices_and_unsupported_mutations(self):
        self.as_user(self.requester)
        response = self.client.get("/api/plugin-ticket/companies/", **self.header)
        self.assertEqual(response.status_code, 200)
        self.assertEqual([row["id"] for row in response.data], [self.a.pk])
        self.assertEqual(self.client.patch(f"{self.url}{self.own.pk}/", {"title": "Edited"}, **self.header).status_code, 405)
        self.assertEqual(self.client.delete(f"{self.url}{self.own.pk}/", **self.header).status_code, 405)

    def test_model_guard_and_admin_access(self):
        invalid = Ticket(workspace=self.workspace, company=self.foreign, requester=self.requester,
                         title="Invalid", description="No")
        with self.assertRaises(ValidationError):
            invalid.full_clean()
        request = RequestFactory().get("/admin/")
        self.requester.is_staff = True
        request.user = self.requester
        self.assertFalse(admin.site._registry[Ticket].has_module_permission(request))
        request.user = User.objects.create_superuser("ticket-root", "ticket-root@example.test", password="unused")
        self.assertTrue(admin.site._registry[Ticket].has_module_permission(request))
