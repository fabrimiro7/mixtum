from rest_framework import serializers
from .models import Link


class LinkSerializer(serializers.ModelSerializer):
    label_display = serializers.CharField(source="get_label_display", read_only=True)

    class Meta:
        model = Link
        fields = (
            "id",
            "workspace",
            "label",
            "label_display",
            "title",
            "description",
            "url",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "workspace", "created_at", "updated_at")
