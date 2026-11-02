import uuid

from django.conf import settings
from django.db import models


class AiProvider(models.Model):
    REGOLO = "regolo"
    OPENAI_COMPATIBLE = "openai_compatible"
    KINDS = ((REGOLO, "Regolo"), (OPENAI_COMPATIBLE, "OpenAI compatible"))

    name = models.CharField(max_length=120, unique=True)
    kind = models.CharField(max_length=32, choices=KINDS)
    base_url = models.URLField(max_length=500)
    api_key_env_var = models.CharField(max_length=120, blank=True, default="")
    enabled = models.BooleanField(default=True)
    timeout_seconds = models.PositiveSmallIntegerField(default=120)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class AiModel(models.Model):
    provider = models.ForeignKey(AiProvider, on_delete=models.PROTECT, related_name="models")
    model_id = models.CharField(max_length=255)
    display_name = models.CharField(max_length=255)
    capabilities = models.JSONField(default=list, blank=True)
    prompt_cost_per_million = models.DecimalField(max_digits=14, decimal_places=6, null=True, blank=True)
    completion_cost_per_million = models.DecimalField(max_digits=14, decimal_places=6, null=True, blank=True)
    enabled = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=("provider", "model_id"), name="ai_model_provider_id_uniq")]


class WorkspaceAiPolicy(models.Model):
    workspace = models.OneToOneField(
        "workspace.Workspace", on_delete=models.CASCADE, related_name="ai_policy",
    )
    monthly_budget_microunits = models.PositiveBigIntegerField(null=True, blank=True)
    monthly_token_budget = models.PositiveBigIntegerField(null=True, blank=True)
    max_run_tokens = models.PositiveIntegerField(default=100000)
    debug_enabled_until = models.DateTimeField(null=True, blank=True)
    metadata_retention_days = models.PositiveSmallIntegerField(default=90)
    debug_retention_days = models.PositiveSmallIntegerField(default=7)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class ToolDefinition(models.Model):
    workspace = models.ForeignKey(
        "workspace.Workspace", on_delete=models.CASCADE, null=True, blank=True, related_name="ai_tools",
    )
    key = models.CharField(max_length=160)
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, default="")
    input_schema = models.JSONField(default=dict, blank=True)
    output_schema = models.JSONField(default=dict, blank=True)
    permission = models.CharField(max_length=160, blank=True, default="")
    side_effect = models.BooleanField(default=False)
    requires_approval = models.BooleanField(default=False)
    timeout_seconds = models.PositiveSmallIntegerField(default=30)
    enabled = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=("workspace", "key"), name="ai_tool_workspace_key_uniq")]


class Agent(models.Model):
    workspace = models.ForeignKey("workspace.Workspace", on_delete=models.CASCADE, related_name="ai_agents")
    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=160)
    description = models.TextField(blank=True, default="")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="created_ai_agents")
    published_version = models.ForeignKey(
        "AgentVersion", on_delete=models.SET_NULL, null=True, blank=True, related_name="published_for_agents",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=("workspace", "slug"), name="ai_agent_workspace_slug_uniq")]


class AgentVersion(models.Model):
    agent = models.ForeignKey(Agent, on_delete=models.CASCADE, related_name="versions")
    version = models.PositiveIntegerField()
    model = models.ForeignKey(AiModel, on_delete=models.PROTECT, related_name="agent_versions")
    system_prompt = models.TextField()
    input_schema = models.JSONField(default=dict, blank=True)
    output_schema = models.JSONField(default=dict, blank=True)
    config = models.JSONField(default=dict, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=("agent", "version"), name="ai_agent_version_uniq")]


class AgentVersionTool(models.Model):
    agent_version = models.ForeignKey(AgentVersion, on_delete=models.CASCADE, related_name="tool_assignments")
    tool = models.ForeignKey(ToolDefinition, on_delete=models.PROTECT, related_name="agent_assignments")
    order = models.PositiveSmallIntegerField(default=0)
    config = models.JSONField(default=dict, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=("agent_version", "tool"), name="ai_agent_version_tool_uniq"),
            models.UniqueConstraint(fields=("agent_version", "order"), name="ai_agent_version_tool_order_uniq"),
        ]


class Flow(models.Model):
    workspace = models.ForeignKey("workspace.Workspace", on_delete=models.CASCADE, related_name="ai_flows")
    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=160)
    description = models.TextField(blank=True, default="")
    draft_graph = models.JSONField(default=dict, blank=True)
    draft_input_schema = models.JSONField(default=dict, blank=True)
    draft_output_schema = models.JSONField(default=dict, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="created_ai_flows")
    published_version = models.ForeignKey(
        "FlowVersion", on_delete=models.SET_NULL, null=True, blank=True, related_name="published_for_flows",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=("workspace", "slug"), name="ai_flow_workspace_slug_uniq")]


class FlowVersion(models.Model):
    flow = models.ForeignKey(Flow, on_delete=models.CASCADE, related_name="versions")
    version = models.PositiveIntegerField()
    graph = models.JSONField()
    input_schema = models.JSONField(default=dict, blank=True)
    output_schema = models.JSONField(default=dict, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=("flow", "version"), name="ai_flow_version_uniq")]


class Run(models.Model):
    FLOW = "flow"
    AGENT = "agent"
    INGESTION = "ingestion"
    RETRIEVAL = "retrieval"
    KINDS = ((FLOW, "Flow"), (AGENT, "Agent"), (INGESTION, "Ingestion"), (RETRIEVAL, "Retrieval"))
    PENDING = "pending"
    RUNNING = "running"
    AWAITING_APPROVAL = "awaiting_approval"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    STATUSES = (
        (PENDING, "Pending"), (RUNNING, "Running"), (AWAITING_APPROVAL, "Awaiting approval"),
        (COMPLETED, "Completed"), (FAILED, "Failed"), (CANCELLED, "Cancelled"),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    kind = models.CharField(max_length=16, choices=KINDS, default=FLOW)
    workspace = models.ForeignKey("workspace.Workspace", on_delete=models.PROTECT, related_name="ai_runs")
    flow_version = models.ForeignKey(FlowVersion, on_delete=models.PROTECT, null=True, blank=True, related_name="runs")
    agent_version = models.ForeignKey(AgentVersion, on_delete=models.PROTECT, null=True, blank=True, related_name="runs")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="ai_runs")
    source_product = models.CharField(max_length=80, default="ai_labs")
    idempotency_key = models.CharField(max_length=160)
    status = models.CharField(max_length=24, choices=STATUSES, default=PENDING, db_index=True)
    input = models.JSONField(default=dict, blank=True)
    output = models.JSONField(default=dict, blank=True)
    state = models.JSONField(default=dict, blank=True)
    error_code = models.CharField(max_length=80, blank=True, default="")
    error_message = models.TextField(blank=True, default="")
    prompt_tokens = models.PositiveIntegerField(null=True, blank=True)
    completion_tokens = models.PositiveIntegerField(null=True, blank=True)
    total_tokens = models.PositiveIntegerField(null=True, blank=True)
    cost_microunits = models.PositiveBigIntegerField(null=True, blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    ended_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("workspace", "source_product", "idempotency_key"), name="ai_run_idempotency_uniq",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(kind="flow", flow_version__isnull=False, agent_version__isnull=True)
                    | models.Q(kind="agent", flow_version__isnull=True, agent_version__isnull=False)
                    | models.Q(kind="ingestion", flow_version__isnull=True, agent_version__isnull=True)
                    | models.Q(kind="retrieval", flow_version__isnull=True, agent_version__isnull=True)
                ),
                name="ai_run_definition_matches_kind",
            ),
        ]
        indexes = [models.Index(fields=("workspace", "created_at"), name="ai_run_workspace_created_idx")]


class RunEvent(models.Model):
    run = models.ForeignKey(Run, on_delete=models.CASCADE, related_name="events")
    sequence = models.PositiveIntegerField()
    event_type = models.CharField(max_length=80)
    node_id = models.CharField(max_length=120, blank=True, default="")
    metadata = models.JSONField(default=dict, blank=True)
    debug_content = models.JSONField(null=True, blank=True)
    debug_expires_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=("run", "sequence"), name="ai_run_event_sequence_uniq")]
        ordering = ("sequence",)


class BudgetReservation(models.Model):
    RESERVED = "reserved"
    RECONCILED = "reconciled"
    ESTIMATED = "estimated"
    RELEASED = "released"
    STATUSES = ((RESERVED, "Reserved"), (RECONCILED, "Reconciled"), (ESTIMATED, "Estimated"), (RELEASED, "Released"))

    run = models.ForeignKey(Run, on_delete=models.CASCADE, related_name="budget_reservations")
    workspace = models.ForeignKey("workspace.Workspace", on_delete=models.CASCADE, related_name="ai_budget_reservations")
    reservation_key = models.CharField(max_length=160)
    period_start = models.DateField(db_index=True)
    estimated_tokens = models.PositiveIntegerField()
    estimated_cost_microunits = models.PositiveBigIntegerField(null=True, blank=True)
    actual_tokens = models.PositiveIntegerField(null=True, blank=True)
    actual_cost_microunits = models.PositiveBigIntegerField(null=True, blank=True)
    status = models.CharField(max_length=16, choices=STATUSES, default=RESERVED)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=("run", "reservation_key"), name="ai_budget_reservation_uniq")]
        indexes = [models.Index(fields=("workspace", "period_start", "status"), name="ai_budget_period_idx")]


class ApprovalRequest(models.Model):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    STATUSES = ((PENDING, "Pending"), (APPROVED, "Approved"), (REJECTED, "Rejected"))

    run = models.ForeignKey(Run, on_delete=models.CASCADE, related_name="approvals")
    node_id = models.CharField(max_length=120)
    request_fingerprint = models.CharField(max_length=64)
    payload = models.JSONField(default=dict, blank=True)
    status = models.CharField(max_length=16, choices=STATUSES, default=PENDING)
    requested_at = models.DateTimeField(auto_now_add=True)
    decided_at = models.DateTimeField(null=True, blank=True)
    decided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name="decided_ai_approvals",
    )

    class Meta:
        constraints = [models.UniqueConstraint(fields=("run", "node_id"), name="ai_approval_run_node_uniq")]


class KnowledgeBase(models.Model):
    workspace = models.ForeignKey("workspace.Workspace", on_delete=models.CASCADE, related_name="ai_knowledge_bases")
    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=160)
    embedding_model = models.ForeignKey(AiModel, on_delete=models.PROTECT, related_name="knowledge_bases")
    vector_size = models.PositiveIntegerField()
    index_generation = models.PositiveIntegerField(default=1)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=("workspace", "slug"), name="ai_kb_workspace_slug_uniq")]


class KnowledgeSource(models.Model):
    UPLOAD = "upload"
    PRODUCT = "product"
    TYPES = ((UPLOAD, "Upload AI Labs"), (PRODUCT, "Risorsa prodotto"))
    WORKSPACE = "workspace"
    PRIVATE = "private"
    VISIBILITIES = ((WORKSPACE, "Workspace"), (PRIVATE, "Privata"))

    knowledge_base = models.ForeignKey(KnowledgeBase, on_delete=models.CASCADE, related_name="sources")
    source_type = models.CharField(max_length=16, choices=TYPES)
    adapter_key = models.CharField(max_length=160, blank=True, default="")
    resource_id = models.CharField(max_length=255, blank=True, default="")
    title = models.CharField(max_length=500)
    visibility = models.CharField(max_length=16, choices=VISIBILITIES, default=WORKSPACE)
    uploaded_file = models.FileField(upload_to="ai_labs/sources/", null=True, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=(
                    (models.Q(source_type="upload", adapter_key="", resource_id="") & ~models.Q(uploaded_file=""))
                    | (models.Q(source_type="product", uploaded_file="")
                       & ~models.Q(adapter_key="") & ~models.Q(resource_id=""))
                ),
                name="ai_source_reference_shape",
            ),
        ]


class KnowledgeRevision(models.Model):
    PENDING = "pending"
    INDEXING = "indexing"
    READY = "ready"
    FAILED = "failed"
    DELETED = "deleted"
    STATUSES = (
        (PENDING, "Pending"), (INDEXING, "Indexing"), (READY, "Ready"),
        (FAILED, "Failed"), (DELETED, "Deleted"),
    )
    source = models.ForeignKey(KnowledgeSource, on_delete=models.CASCADE, related_name="revisions")
    version = models.PositiveIntegerField()
    checksum = models.CharField(max_length=64)
    status = models.CharField(max_length=16, choices=STATUSES, default=PENDING, db_index=True)
    index_generation = models.PositiveIntegerField()
    error_message = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    indexed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=("source", "version"), name="ai_source_revision_uniq")]


class KnowledgeChunk(models.Model):
    revision = models.ForeignKey(KnowledgeRevision, on_delete=models.CASCADE, related_name="chunks")
    ordinal = models.PositiveIntegerField()
    page = models.PositiveIntegerField(null=True, blank=True)
    area = models.JSONField(null=True, blank=True)
    text = models.TextField()
    vector_point_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=("revision", "ordinal"), name="ai_revision_chunk_uniq")]
        ordering = ("ordinal",)
