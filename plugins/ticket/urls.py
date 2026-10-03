from django.urls import path

from .views import ClientCompanyListView, TicketDetailView, TicketListCreateView


urlpatterns = [
    path("companies/", ClientCompanyListView.as_view(), name="ticket-companies"),
    path("tickets/", TicketListCreateView.as_view(), name="ticket-list"),
    path("tickets/<int:pk>/", TicketDetailView.as_view(), name="ticket-detail"),
]
