from django.db import IntegrityError, transaction
from django.db.models.deletion import ProtectedError
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.pagination import LimitOffsetPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from base_modules.user_manager.models import User
from base_modules.workspace.models import AdminAuditEvent
from base_modules.workspace.permissions import HasManagedWorkspace, HasSelectedWorkspace
from base_modules.workspace.services import record_admin_event

from .models import AssistanceManager, ClientCompany, CompanyMembership, OperatorGrant
from .serializers import (
    AssistanceManagerSerializer,
    ClientCompanySerializer,
    CompanyMembershipSerializer,
    OperatorGrantSerializer,
    TicketCompanyConfigurationSerializer,
    TicketCreateSerializer,
    TicketReadSerializer,
    TicketUserSerializer,
    UserRoleAssignmentSerializer,
)
from .services import (
    companies_for_requester,
    configure_company_membership,
    configure_manager,
    configure_operator,
    create_ticket,
    visible_tickets,
)


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


class TicketConfigurationView(APIView):
    permission_classes = (IsAuthenticated, HasManagedWorkspace)

    def get(self, request):
        companies = ClientCompany.objects.filter(workspace=request.workspace).prefetch_related(
            "memberships__user", "operator_grants__user",
        )
        managers = AssistanceManager.objects.filter(workspace=request.workspace).select_related("user")
        users = User.objects.filter(
            is_active=True, workspaceuser__workspace=request.workspace,
        ).distinct()
        return Response({
            "companies": TicketCompanyConfigurationSerializer(companies, many=True).data,
            "managers": AssistanceManagerSerializer(managers, many=True).data,
            "available_users": TicketUserSerializer(users, many=True).data,
        })


class TicketCompanyCreateView(APIView):
    permission_classes = (IsAuthenticated, HasManagedWorkspace)

    def post(self, request):
        serializer = TicketCompanyConfigurationSerializer(
            data=request.data, context={"workspace": request.workspace},
        )
        serializer.is_valid(raise_exception=True)
        try:
            with transaction.atomic():
                company = serializer.save(workspace=request.workspace)
                record_admin_event(
                    actor=request.user, action="ticket.company.create", outcome=AdminAuditEvent.SUCCESS,
                    workspace=request.workspace,
                )
        except IntegrityError:
            raise ValidationError({
                "name": "Esiste già un'azienda con questo nome nel workspace.",
            }) from None
        return Response(TicketCompanyConfigurationSerializer(company).data, status=status.HTTP_201_CREATED)


class TicketCompanyDetailView(APIView):
    permission_classes = (IsAuthenticated, HasManagedWorkspace)

    def patch(self, request, pk):
        company = get_object_or_404(ClientCompany, pk=pk, workspace=request.workspace)
        serializer = TicketCompanyConfigurationSerializer(
            company, data=request.data, partial=True, context={"workspace": request.workspace},
        )
        serializer.is_valid(raise_exception=True)
        try:
            with transaction.atomic():
                serializer.save()
                record_admin_event(
                    actor=request.user, action="ticket.company.update", outcome=AdminAuditEvent.SUCCESS,
                    workspace=request.workspace,
                )
        except IntegrityError:
            raise ValidationError({
                "name": "Esiste già un'azienda con questo nome nel workspace.",
            }) from None
        return Response(serializer.data)

    def delete(self, request, pk):
        company = get_object_or_404(ClientCompany, pk=pk, workspace=request.workspace)
        try:
            company.delete()
        except ProtectedError:
            return Response(
                {"detail": "L'azienda con Ticket esistenti non può essere rimossa."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        record_admin_event(
            actor=request.user, action="ticket.company.delete", outcome=AdminAuditEvent.SUCCESS,
            workspace=request.workspace,
        )
        return Response(status=status.HTTP_204_NO_CONTENT)


class CompanyMembershipCreateView(APIView):
    permission_classes = (IsAuthenticated, HasManagedWorkspace)

    def post(self, request, company_id):
        serializer = UserRoleAssignmentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        membership = configure_company_membership(
            workspace=request.workspace,
            company_id=company_id,
            user_id=serializer.validated_data["user_id"],
            role=serializer.validated_data.get("role", CompanyMembership.REQUESTER),
        )
        record_admin_event(
            actor=request.user, action="ticket.company_membership.create",
            outcome=AdminAuditEvent.SUCCESS, workspace=request.workspace, target_user=membership.user,
        )
        return Response(CompanyMembershipSerializer(membership).data, status=status.HTTP_201_CREATED)


class CompanyMembershipDetailView(APIView):
    permission_classes = (IsAuthenticated, HasManagedWorkspace)

    def _membership(self, request, pk):
        return get_object_or_404(
            CompanyMembership.objects.select_related("user", "company"),
            pk=pk, company__workspace=request.workspace,
        )

    def patch(self, request, pk):
        membership = self._membership(request, pk)
        serializer = UserRoleAssignmentSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        if "user_id" in serializer.validated_data:
            raise ValidationError({"user_id": "L'utente non è modificabile."})
        if "role" in serializer.validated_data:
            membership.role = serializer.validated_data["role"]
            membership.save(update_fields=("role",))
        record_admin_event(
            actor=request.user, action="ticket.company_membership.update",
            outcome=AdminAuditEvent.SUCCESS, workspace=request.workspace, target_user=membership.user,
        )
        return Response(CompanyMembershipSerializer(membership).data)

    def delete(self, request, pk):
        membership = self._membership(request, pk)
        target_user = membership.user
        membership.delete()
        record_admin_event(
            actor=request.user, action="ticket.company_membership.delete",
            outcome=AdminAuditEvent.SUCCESS, workspace=request.workspace, target_user=target_user,
        )
        return Response(status=status.HTTP_204_NO_CONTENT)


class OperatorGrantCreateView(APIView):
    permission_classes = (IsAuthenticated, HasManagedWorkspace)

    def post(self, request, company_id):
        serializer = UserRoleAssignmentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        grant = configure_operator(
            workspace=request.workspace, company_id=company_id,
            user_id=serializer.validated_data["user_id"],
        )
        record_admin_event(
            actor=request.user, action="ticket.operator.create", outcome=AdminAuditEvent.SUCCESS,
            workspace=request.workspace, target_user=grant.user,
        )
        return Response(OperatorGrantSerializer(grant).data, status=status.HTTP_201_CREATED)


class OperatorGrantDeleteView(APIView):
    permission_classes = (IsAuthenticated, HasManagedWorkspace)

    def delete(self, request, pk):
        grant = get_object_or_404(
            OperatorGrant.objects.select_related("user", "company"),
            pk=pk, company__workspace=request.workspace,
        )
        target_user = grant.user
        grant.delete()
        record_admin_event(
            actor=request.user, action="ticket.operator.delete", outcome=AdminAuditEvent.SUCCESS,
            workspace=request.workspace, target_user=target_user,
        )
        return Response(status=status.HTTP_204_NO_CONTENT)


class AssistanceManagerListCreateView(APIView):
    permission_classes = (IsAuthenticated, HasManagedWorkspace)

    def post(self, request):
        serializer = UserRoleAssignmentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        manager = configure_manager(
            workspace=request.workspace, user_id=serializer.validated_data["user_id"],
        )
        record_admin_event(
            actor=request.user, action="ticket.manager.create", outcome=AdminAuditEvent.SUCCESS,
            workspace=request.workspace, target_user=manager.user,
        )
        return Response(AssistanceManagerSerializer(manager).data, status=status.HTTP_201_CREATED)


class AssistanceManagerDeleteView(APIView):
    permission_classes = (IsAuthenticated, HasManagedWorkspace)

    def delete(self, request, pk):
        manager = get_object_or_404(
            AssistanceManager.objects.select_related("user"), pk=pk, workspace=request.workspace,
        )
        target_user = manager.user
        manager.delete()
        record_admin_event(
            actor=request.user, action="ticket.manager.delete", outcome=AdminAuditEvent.SUCCESS,
            workspace=request.workspace, target_user=target_user,
        )
        return Response(status=status.HTTP_204_NO_CONTENT)
