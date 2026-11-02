from rest_framework import serializers

from .graph import validate_graph
from .models import (
    Agent, AgentVersion, AiModel, AiProvider, ApprovalRequest, Flow, FlowVersion, KnowledgeBase,
    KnowledgeRevision, KnowledgeSource, Run, RunEvent, ToolDefinition, WorkspaceAiPolicy,
)
from .providers import validate_provider_url


class AiProviderSerializer(serializers.ModelSerializer):
    class Meta:
        model = AiProvider
        fields = (
            "id", "name", "kind", "base_url", "api_key_env_var", "enabled", "timeout_seconds",
            "created_at", "updated_at",
        )
        read_only_fields = ("id", "created_at", "updated_at")

    def validate_base_url(self, value):
        # DNS is intentionally revalidated immediately before each request. At
        # configuration time the target can be temporarily unavailable.
        return validate_provider_url(value, resolve=False)


class AiModelSerializer(serializers.ModelSerializer):
    provider_name = serializers.CharField(source="provider.name", read_only=True)

    class Meta:
        model = AiModel
        fields = (
            "id", "provider", "provider_name", "model_id", "display_name", "capabilities",
            "prompt_cost_per_million", "completion_cost_per_million", "enabled", "created_at", "updated_at",
        )
        read_only_fields = ("id", "created_at", "updated_at")

    def validate_capabilities(self, value):
        allowed = {"chat", "tools", "vision", "embedding", "ocr"}
        if not isinstance(value, list) or not all(isinstance(item, str) and item in allowed for item in value):
            raise serializers.ValidationError("Capability modello non valide.")
        return sorted(set(value))


class WorkspaceAiPolicySerializer(serializers.ModelSerializer):
    class Meta:
        model = WorkspaceAiPolicy
        fields = (
            "workspace", "monthly_budget_microunits", "monthly_token_budget", "max_run_tokens",
            "debug_enabled_until", "metadata_retention_days", "debug_retention_days", "updated_at",
        )
        read_only_fields = ("workspace", "updated_at")

    def validate(self, attrs):
        for field in ("metadata_retention_days", "debug_retention_days"):
            value = attrs.get(field, getattr(self.instance, field, None))
            if value is not None and not 1 <= value <= 3650:
                raise serializers.ValidationError({field: "Valore ammesso: 1..3650 giorni."})
        return attrs


class ToolDefinitionSerializer(serializers.ModelSerializer):
    class Meta:
        model = ToolDefinition
        fields = (
            "id", "key", "name", "description", "input_schema", "output_schema", "permission",
            "side_effect", "requires_approval", "timeout_seconds", "enabled",
        )
        read_only_fields = fields


class AgentVersionSerializer(serializers.ModelSerializer):
    tools = serializers.SerializerMethodField()

    class Meta:
        model = AgentVersion
        fields = (
            "id", "version", "model", "system_prompt", "input_schema", "output_schema", "config", "tools", "created_at",
        )

    def get_tools(self, obj):
        return [assignment.tool.key for assignment in obj.tool_assignments.select_related("tool").order_by("order")]


class AgentSerializer(serializers.ModelSerializer):
    published_version = AgentVersionSerializer(read_only=True)

    class Meta:
        model = Agent
        fields = ("id", "name", "slug", "description", "published_version", "created_at", "updated_at")
        read_only_fields = ("id", "published_version", "created_at", "updated_at")


class AgentPublishSerializer(serializers.Serializer):
    model_id = serializers.PrimaryKeyRelatedField(queryset=AiModel.objects.filter(enabled=True), source="model")
    system_prompt = serializers.CharField(max_length=100000)
    input_schema = serializers.JSONField(default=dict)
    output_schema = serializers.JSONField(default=dict)
    config = serializers.JSONField(default=dict)
    tool_ids = serializers.ListField(child=serializers.IntegerField(min_value=1), default=list)


class FlowVersionSerializer(serializers.ModelSerializer):
    class Meta:
        model = FlowVersion
        fields = ("id", "version", "graph", "input_schema", "output_schema", "created_at")


class FlowSerializer(serializers.ModelSerializer):
    published_version = FlowVersionSerializer(read_only=True)

    class Meta:
        model = Flow
        fields = (
            "id", "name", "slug", "description", "draft_graph", "draft_input_schema", "draft_output_schema",
            "published_version", "created_at", "updated_at",
        )
        read_only_fields = ("id", "published_version", "created_at", "updated_at")

    def validate_draft_graph(self, value):
        validate_graph(value)
        return value


class RunEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = RunEvent
        fields = ("sequence", "event_type", "node_id", "metadata", "debug_content", "debug_expires_at", "created_at")


class RunSerializer(serializers.ModelSerializer):
    events = RunEventSerializer(many=True, read_only=True)
    approvals = serializers.SerializerMethodField()

    class Meta:
        model = Run
        fields = (
            "id", "kind", "flow_version", "agent_version", "source_product", "status", "input", "output", "error_code",
            "error_message", "prompt_tokens", "completion_tokens", "total_tokens", "cost_microunits",
            "started_at", "ended_at", "created_at", "events", "approvals",
        )

    def get_approvals(self, obj):
        return [
            {"id": item.pk, "node_id": item.node_id, "status": item.status, "payload": item.payload,
             "requested_at": item.requested_at, "decided_at": item.decided_at}
            for item in obj.approvals.order_by("requested_at")
        ]


class RunCreateSerializer(serializers.Serializer):
    input = serializers.JSONField(default=dict)
    source_product = serializers.RegexField(r"[a-z][a-z0-9_-]{0,79}", default="ai_labs")
    idempotency_key = serializers.CharField(max_length=160)


class ApprovalDecisionSerializer(serializers.Serializer):
    approve = serializers.BooleanField()


class KnowledgeRevisionSerializer(serializers.ModelSerializer):
    chunk_count = serializers.IntegerField(source="chunks.count", read_only=True)

    class Meta:
        model = KnowledgeRevision
        fields = (
            "id", "version", "checksum", "status", "index_generation", "error_message",
            "chunk_count", "created_at", "indexed_at",
        )
        read_only_fields = fields


class KnowledgeSourceSerializer(serializers.ModelSerializer):
    revisions = KnowledgeRevisionSerializer(many=True, read_only=True)

    class Meta:
        model = KnowledgeSource
        fields = (
            "id", "knowledge_base", "source_type", "adapter_key", "resource_id", "title",
            "visibility", "uploaded_file", "revisions", "created_at", "updated_at",
        )
        read_only_fields = ("id", "knowledge_base", "revisions", "created_at", "updated_at")
        extra_kwargs = {"uploaded_file": {"write_only": True}}

    def validate(self, attrs):
        source_type = attrs.get("source_type", getattr(self.instance, "source_type", None))
        uploaded_file = attrs.get("uploaded_file", getattr(self.instance, "uploaded_file", None))
        adapter_key = attrs.get("adapter_key", getattr(self.instance, "adapter_key", ""))
        resource_id = attrs.get("resource_id", getattr(self.instance, "resource_id", ""))
        if source_type == KnowledgeSource.UPLOAD:
            if not uploaded_file:
                raise serializers.ValidationError({"uploaded_file": "File obbligatorio."})
            if uploaded_file.size > 25 * 1024 * 1024:
                raise serializers.ValidationError({"uploaded_file": "Dimensione massima: 25 MiB."})
            if adapter_key or resource_id:
                raise serializers.ValidationError("Un upload non può indicare un adapter di prodotto.")
        elif source_type == KnowledgeSource.PRODUCT:
            if uploaded_file or not adapter_key or not resource_id:
                raise serializers.ValidationError("Una sorgente prodotto richiede adapter_key e resource_id, senza file.")
        return attrs


class KnowledgeBaseSerializer(serializers.ModelSerializer):
    class Meta:
        model = KnowledgeBase
        fields = (
            "id", "name", "slug", "embedding_model", "vector_size", "index_generation",
            "created_at", "updated_at",
        )
        read_only_fields = ("id", "index_generation", "created_at", "updated_at")

    def validate_embedding_model(self, value):
        if "embedding" not in value.capabilities or not value.enabled or not value.provider.enabled:
            raise serializers.ValidationError("Il modello non è un modello embedding attivo.")
        return value


class KnowledgeSearchSerializer(serializers.Serializer):
    query = serializers.CharField(max_length=20000)
    limit = serializers.IntegerField(min_value=1, max_value=20, default=8)
    idempotency_key = serializers.CharField(max_length=160)
