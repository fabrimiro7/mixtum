from base_modules.user_manager.serializers import UserDetailSerializer
from rest_framework import serializers
from django.urls import reverse

from .models import Attachment

MAX_ATTACHMENT_BYTES = 20 * 1024 * 1024


class AttachmentSerializer(serializers.ModelSerializer):
    author = UserDetailSerializer()
    file = serializers.SerializerMethodField()

    def get_file(self, obj):
        if not obj.file:
            return None
        url = reverse("attachment:attachment-download", kwargs={"pk": obj.pk})
        request = self.context.get("request")
        return request.build_absolute_uri(url) if request else url
    
    class Meta:
        model = Attachment
        fields = ['id', 'title', 'author', 'creation_date', 'file', 'description']
        read_only_fields = ['author', 'creation_date']

class AttachmentEditSerializer(serializers.ModelSerializer):
    def validate_file(self, value):
        if value.size > MAX_ATTACHMENT_BYTES:
            raise serializers.ValidationError("L'allegato supera il limite di 20 MiB.")
        return value

    class Meta:
        model = Attachment
        fields = ['id', 'title', 'author', 'creation_date', 'file', 'description']
        read_only_fields = ['author', 'creation_date']
