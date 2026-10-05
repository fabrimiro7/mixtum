from rest_framework import serializers

from base_modules.user_manager.models import User

from .models import AssistanceManager, ClientCompany, CompanyMembership, OperatorGrant, Ticket


class TicketUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ("id", "username", "email")
        read_only_fields = fields


class CompanyMembershipSerializer(serializers.ModelSerializer):
    user = TicketUserSerializer(read_only=True)

    class Meta:
        model = CompanyMembership
        fields = ("id", "user", "role")
        read_only_fields = fields


class OperatorGrantSerializer(serializers.ModelSerializer):
    user = TicketUserSerializer(read_only=True)

    class Meta:
        model = OperatorGrant
        fields = ("id", "user")
        read_only_fields = fields


class AssistanceManagerSerializer(serializers.ModelSerializer):
    user = TicketUserSerializer(read_only=True)

    class Meta:
        model = AssistanceManager
        fields = ("id", "user")
        read_only_fields = fields


class TicketCompanyConfigurationSerializer(serializers.ModelSerializer):
    memberships = CompanyMembershipSerializer(many=True, read_only=True)
    operator_grants = OperatorGrantSerializer(many=True, read_only=True)

    class Meta:
        model = ClientCompany
        fields = ("id", "name", "memberships", "operator_grants")
        read_only_fields = ("id", "memberships", "operator_grants")

    def validate_name(self, value):
        workspace = self.context.get("workspace")
        if workspace is None and self.instance is not None:
            workspace = self.instance.workspace
        if workspace is not None:
            existing = ClientCompany.objects.filter(workspace=workspace, name=value)
            if self.instance is not None:
                existing = existing.exclude(pk=self.instance.pk)
            if existing.exists():
                raise serializers.ValidationError("Esiste già un'azienda con questo nome nel workspace.")
        return value


class UserRoleAssignmentSerializer(serializers.Serializer):
    user_id = serializers.IntegerField(min_value=1)
    role = serializers.ChoiceField(choices=CompanyMembership.ROLES, required=False)


class ClientCompanySerializer(serializers.ModelSerializer):
    class Meta:
        model = ClientCompany
        fields = ("id", "name")


class TicketReadSerializer(serializers.ModelSerializer):
    company_name = serializers.CharField(source="company.name", read_only=True)

    class Meta:
        model = Ticket
        fields = ("id", "company", "company_name", "title", "description", "status", "created_at")
        read_only_fields = fields


class TicketCreateSerializer(serializers.Serializer):
    company_id = serializers.IntegerField(min_value=1)
    title = serializers.CharField(max_length=255)
    description = serializers.CharField()
