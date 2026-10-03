from django.urls import path

from .views import VisibleTicketSummaryView


urlpatterns = [path("summary/", VisibleTicketSummaryView.as_view(), name="demo-support-summary")]
