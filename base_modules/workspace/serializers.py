# workspace/serializers.py
from base_modules.user_manager.models import User
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers
from .models import Workspace, WorkspaceUser
from .services import change_membership_role, create_membership, create_workspace_with_owner

class UserSerializer(serializers.ModelSerializer):
    """
    Serializer di base per il modello User (per riferimento).
    """
    class Meta:
        model = User
        fields = ['id', 'username', 'email'] 

class WorkspaceSerializer(serializers.ModelSerializer):
    """
    Serializer per il modello Workspace.
    """
    users_count = serializers.SerializerMethodField()
    owner_user_id = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.filter(is_active=True, external_identity__isnull=False),
        source='owner', write_only=True, required=False,
    )
    
    def get_users_count(self, obj):
        return obj.workspaceuser_set.count()

    class Meta:
        model = Workspace
        fields = [
            'id',
            'workspace_name',
            'workspace_description',
            'workspace_logo',
            'created_at',
            'updated_at',
            'users_count',
            'owner_user_id',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'workspace_logo']

    def validate(self, attrs):
        if 'workspace_logo' in self.initial_data:
            raise serializers.ValidationError({
                'workspace_logo': 'Usare il branding workspace per caricare immagini validate.',
            })
        if self.instance is None and 'owner' not in attrs:
            raise serializers.ValidationError({'owner_user_id': 'Il gestore iniziale è obbligatorio.'})
        if self.instance is not None and 'owner' in attrs:
            raise serializers.ValidationError({'owner_user_id': 'Il gestore iniziale non è modificabile.'})
        return attrs

    def create(self, validated_data):
        owner = validated_data.pop('owner')
        try:
            return create_workspace_with_owner(owner=owner, **validated_data)
        except DjangoValidationError as error:
            raise serializers.ValidationError(error.messages) from None

class WorkspaceUserSerializer(serializers.ModelSerializer):
    """
    Serializer per il modello WorkspaceUser.
    """
    user = UserSerializer(read_only=True)
    workspace = WorkspaceSerializer(read_only=True)

    user_id = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(), source='user', write_only=True
    )
    workspace_id = serializers.PrimaryKeyRelatedField(
        queryset=Workspace.objects.all(), source='workspace', write_only=True
    )

    class Meta:
        model = WorkspaceUser
        fields = [
            'id',
            'user',
            'workspace',
            'user_id',      
            'workspace_id', 
            'role',
            'date_joined'
        ]
        read_only_fields = ['id', 'date_joined']

    def validate(self, attrs):
        if self.instance is not None:
            protected = {'user', 'workspace'}.intersection(attrs)
            if protected:
                raise serializers.ValidationError('Utente e workspace non sono modificabili.')
        elif 'user' in attrs and 'workspace' in attrs and WorkspaceUser.objects.filter(
            user=attrs['user'], workspace=attrs['workspace'],
        ).exists():
            raise serializers.ValidationError('La membership esiste già.')
        return attrs

    def create(self, validated_data):
        try:
            return create_membership(**validated_data)
        except DjangoValidationError as error:
            raise serializers.ValidationError(error.messages) from None

    def update(self, instance, validated_data):
        role = validated_data.get('role', instance.role)
        try:
            return change_membership_role(membership=instance, role=role)
        except DjangoValidationError as error:
            raise serializers.ValidationError(error.messages) from None
