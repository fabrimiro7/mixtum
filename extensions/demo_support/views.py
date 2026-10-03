from django.db.models import Count
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from base_modules.workspace.permissions import HasSelectedWorkspace
from plugins.ticket.services import visible_tickets


class VisibleTicketSummaryView(APIView):
    permission_classes = (IsAuthenticated, HasSelectedWorkspace)

    def get(self, request):
        # Reuse Ticket's public visibility contract; never aggregate before authorization.
        counts = visible_tickets(user=request.user, workspace=request.workspace).values("status").annotate(
            count=Count("id")
        )
        by_status = {row["status"]: row["count"] for row in counts}
        return Response({"open": by_status.get("open", 0), "closed": by_status.get("closed", 0)})
