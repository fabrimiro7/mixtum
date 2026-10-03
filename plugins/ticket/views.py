from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.pagination import LimitOffsetPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from base_modules.workspace.permissions import HasSelectedWorkspace

from .serializers import ClientCompanySerializer, TicketCreateSerializer, TicketReadSerializer
from .services import companies_for_requester, create_ticket, visible_tickets


class TicketPagination(LimitOffsetPagination):
    default_limit = 50
    max_limit = 100


class ClientCompanyListView(APIView):
    permission_classes = (IsAuthenticated, HasSelectedWorkspace)

    def get(self, request):
        companies = companies_for_requester(user=request.user, workspace=request.workspace)
        return Response(ClientCompanySerializer(companies, many=True).data)


class TicketListCreateView(APIView):
    permission_classes = (IsAuthenticated, HasSelectedWorkspace)

    def get(self, request):
        tickets = visible_tickets(user=request.user, workspace=request.workspace)
        paginator = TicketPagination()
        page = paginator.paginate_queryset(tickets, request, view=self)
        return paginator.get_paginated_response(TicketReadSerializer(page, many=True).data)

    def post(self, request):
        serializer = TicketCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        ticket = create_ticket(user=request.user, workspace=request.workspace, **serializer.validated_data)
        return Response(TicketReadSerializer(ticket).data, status=status.HTTP_201_CREATED)


class TicketDetailView(APIView):
    permission_classes = (IsAuthenticated, HasSelectedWorkspace)

    def get(self, request, pk):
        ticket = get_object_or_404(visible_tickets(user=request.user, workspace=request.workspace), pk=pk)
        return Response(TicketReadSerializer(ticket).data)
