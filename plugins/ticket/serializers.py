from rest_framework import serializers

from .models import ClientCompany, Ticket


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
