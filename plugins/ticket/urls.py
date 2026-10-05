from django.urls import path

from .views import (
    AssistanceManagerDeleteView,
    AssistanceManagerListCreateView,
    ClientCompanyListView,
    CompanyMembershipCreateView,
    CompanyMembershipDetailView,
    OperatorGrantCreateView,
    OperatorGrantDeleteView,
    TicketCompanyCreateView,
    TicketCompanyDetailView,
    TicketConfigurationView,
    TicketDetailView,
    TicketListCreateView,
)


urlpatterns = [
    path("companies/", ClientCompanyListView.as_view(), name="ticket-companies"),
    path("tickets/", TicketListCreateView.as_view(), name="ticket-list"),
    path("tickets/<int:pk>/", TicketDetailView.as_view(), name="ticket-detail"),
    path("configuration/", TicketConfigurationView.as_view(), name="ticket-configuration"),
    path("configuration/companies/", TicketCompanyCreateView.as_view(), name="ticket-company-create"),
    path("configuration/companies/<int:pk>/", TicketCompanyDetailView.as_view(), name="ticket-company-detail"),
    path(
        "configuration/companies/<int:company_id>/memberships/",
        CompanyMembershipCreateView.as_view(), name="ticket-company-membership-create",
    ),
    path(
        "configuration/memberships/<int:pk>/",
        CompanyMembershipDetailView.as_view(), name="ticket-company-membership-detail",
    ),
    path(
        "configuration/companies/<int:company_id>/operators/",
        OperatorGrantCreateView.as_view(), name="ticket-operator-create",
    ),
    path(
        "configuration/operators/<int:pk>/",
        OperatorGrantDeleteView.as_view(), name="ticket-operator-delete",
    ),
    path(
        "configuration/managers/",
        AssistanceManagerListCreateView.as_view(), name="ticket-manager-create",
    ),
    path(
        "configuration/managers/<int:pk>/",
        AssistanceManagerDeleteView.as_view(), name="ticket-manager-delete",
    ),
]
