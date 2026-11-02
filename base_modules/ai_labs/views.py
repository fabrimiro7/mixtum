from django.db import IntegrityError, transaction
from django.db.models import Q
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework.views import APIView

from base_modules.workspace.models import WorkspaceUser
from base_modules.workspace.permissions import HasManagedWorkspace, HasSelectedWorkspace, IsPlatformAdmin

from .knowledge import create_revision, search_knowledge_base
from .models import (
    Agent, AiModel, AiProvider, ApprovalRequest, Flow, KnowledgeBase, KnowledgeRevision,
    KnowledgeSource, Run, ToolDefinition, WorkspaceAiPolicy,
)
from .serializers import (
    AgentPublishSerializer, AgentSerializer, AiModelSerializer, AiProviderSerializer, ApprovalDecisionSerializer, FlowSerializer,
    KnowledgeBaseSerializer, KnowledgeSearchSerializer, KnowledgeSourceSerializer, RunCreateSerializer,
    RunSerializer, ToolDefinitionSerializer, WorkspaceAiPolicySerializer,
)
from .services import decide_approval, publish_agent, publish_flow, start_agent_run, start_flow_run
from .tasks import execute_run_task, index_revision_task


class AiProviderViewSet(viewsets.ModelViewSet):
    queryset = AiProvider.objects.all().order_by("name")
    serializer_class = AiProviderSerializer
    permission_classes = (IsPlatformAdmin,)


class AiModelViewSet(viewsets.ModelViewSet):
    queryset = AiModel.objects.select_related("provider").all().order_by("provider__name", "display_name")
    serializer_class = AiModelSerializer
    permission_classes = (IsPlatformAdmin,)


class WorkspaceAiPolicyView(APIView):
    permission_classes = (IsAuthenticated, HasManagedWorkspace)

    def get(self, request):
        policy, _ = WorkspaceAiPolicy.objects.get_or_create(workspace=request.workspace)
        return Response(WorkspaceAiPolicySerializer(policy).data)

    def patch(self, request):
        if not request.user.is_superuser:
            raise PermissionDenied("Solo l'amministratore centrale può modificare budget e policy AI.")
        policy, _ = WorkspaceAiPolicy.objects.get_or_create(workspace=request.workspace)
        serializer = WorkspaceAiPolicySerializer(policy, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class ToolDefinitionViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = ToolDefinitionSerializer
    permission_classes = (IsAuthenticated, HasManagedWorkspace)

    def get_queryset(self):
        return ToolDefinition.objects.filter(enabled=True).filter(
            Q(workspace=self.request.workspace) | Q(workspace__isnull=True)
        ).order_by("key")


class AgentViewSet(viewsets.ModelViewSet):
    serializer_class = AgentSerializer
    permission_classes = (IsAuthenticated, HasManagedWorkspace)

    def get_queryset(self):
        return Agent.objects.filter(workspace=self.request.workspace).select_related(
            "published_version__model__provider"
        ).prefetch_related("published_version__tool_assignments__tool").order_by("name")

    def perform_create(self, serializer):
        serializer.save(workspace=self.request.workspace, created_by=self.request.user)

    @action(detail=True, methods=("post",))
    def publish(self, request, pk=None):
        serializer = AgentPublishSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        version = publish_agent(agent=self.get_object(), actor=request.user, **serializer.validated_data)
        return Response({"id": version.pk, "version": version.version}, status=status.HTTP_201_CREATED)


class FlowViewSet(viewsets.ModelViewSet):
    serializer_class = FlowSerializer
    permission_classes = (IsAuthenticated, HasManagedWorkspace)

    def get_queryset(self):
        return Flow.objects.filter(workspace=self.request.workspace).select_related("published_version").order_by("name")

    def perform_create(self, serializer):
        serializer.save(workspace=self.request.workspace, created_by=self.request.user)

    @action(detail=True, methods=("post",))
    def publish(self, request, pk=None):
        version = publish_flow(flow=self.get_object(), actor=request.user)
        return Response({"id": version.pk, "version": version.version}, status=status.HTTP_201_CREATED)


class PublishedFlowListView(APIView):
    permission_classes = (IsAuthenticated, HasSelectedWorkspace)

    def get(self, request):
        queryset = Flow.objects.filter(workspace=request.workspace, published_version__isnull=False).select_related("published_version")
        return Response(FlowSerializer(queryset, many=True).data)


class FlowRunCreateView(APIView):
    permission_classes = (IsAuthenticated, HasSelectedWorkspace)

    def post(self, request, flow_id):
        flow = Flow.objects.filter(
            pk=flow_id, workspace=request.workspace, published_version__isnull=False,
        ).select_related("published_version").first()
        if flow is None:
            return Response({"detail": "Flow non disponibile."}, status=status.HTTP_404_NOT_FOUND)
        payload = dict(request.data)
        if "idempotency_key" not in payload and request.headers.get("Idempotency-Key"):
            payload["idempotency_key"] = request.headers["Idempotency-Key"]
        serializer = RunCreateSerializer(data=payload)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        run, created = start_flow_run(
            flow=flow,
            actor=request.user,
            input_data=data["input"],
            idempotency_key=data["idempotency_key"],
            source_product=data["source_product"],
        )
        if created:
            execute_run_task.delay(str(run.pk))
        return Response(RunSerializer(run).data, status=status.HTTP_202_ACCEPTED if created else status.HTTP_200_OK)


class AgentRunCreateView(APIView):
    permission_classes = (IsAuthenticated, HasSelectedWorkspace)

    def post(self, request, agent_id):
        agent = Agent.objects.filter(
            pk=agent_id, workspace=request.workspace, published_version__isnull=False,
        ).select_related("published_version").first()
        if agent is None:
            return Response({"detail": "Agente non disponibile."}, status=status.HTTP_404_NOT_FOUND)
        payload = dict(request.data)
        if "idempotency_key" not in payload and request.headers.get("Idempotency-Key"):
            payload["idempotency_key"] = request.headers["Idempotency-Key"]
        serializer = RunCreateSerializer(data=payload)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        run, created = start_agent_run(
            agent=agent, actor=request.user, input_data=data["input"],
            idempotency_key=data["idempotency_key"], source_product=data["source_product"],
        )
        if created:
            execute_run_task.delay(str(run.pk))
        return Response(RunSerializer(run).data, status=status.HTTP_202_ACCEPTED if created else status.HTTP_200_OK)


class RunViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = RunSerializer
    permission_classes = (IsAuthenticated, HasSelectedWorkspace)

    def get_queryset(self):
        queryset = Run.objects.filter(workspace=self.request.workspace).select_related(
            "flow_version", "agent_version"
        ).prefetch_related("events", "approvals")
        can_manage = self.request.user.is_superuser or WorkspaceUser.objects.filter(
            user=self.request.user, workspace=self.request.workspace, role=WorkspaceUser.OWNER,
        ).exists()
        return queryset if can_manage else queryset.filter(created_by=self.request.user)

    @action(detail=True, methods=("post",))
    def cancel(self, request, pk=None):
        run = self.get_object()
        if run.status not in {Run.PENDING, Run.RUNNING, Run.AWAITING_APPROVAL}:
            return Response({"detail": "Esecuzione non annullabile."}, status=status.HTTP_409_CONFLICT)
        run.status = Run.CANCELLED
        run.save(update_fields=("status", "updated_at"))
        return Response(RunSerializer(run).data)


class ApprovalDecisionView(APIView):
    permission_classes = (IsAuthenticated, HasManagedWorkspace)

    def post(self, request, approval_id):
        approval = ApprovalRequest.objects.select_related("run").filter(
            pk=approval_id, run__workspace=request.workspace,
        ).first()
        if approval is None:
            return Response({"detail": "Approvazione non disponibile."}, status=status.HTTP_404_NOT_FOUND)
        serializer = ApprovalDecisionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        run = decide_approval(approval=approval, actor=request.user, **serializer.validated_data)
        if run.status == Run.PENDING:
            execute_run_task.delay(str(run.pk))
        return Response(RunSerializer(run).data)


class KnowledgeBaseViewSet(viewsets.ModelViewSet):
    serializer_class = KnowledgeBaseSerializer
    permission_classes = (IsAuthenticated, HasManagedWorkspace)

    def get_queryset(self):
        return KnowledgeBase.objects.filter(workspace=self.request.workspace).select_related(
            "embedding_model__provider",
        ).order_by("name")

    def perform_create(self, serializer):
        serializer.save(workspace=self.request.workspace, created_by=self.request.user)

    @action(detail=True, methods=("post",), permission_classes=(IsAuthenticated, HasSelectedWorkspace))
    def search(self, request, pk=None):
        knowledge_base = KnowledgeBase.objects.filter(pk=pk, workspace=request.workspace).select_related(
            "embedding_model__provider",
        ).first()
        if knowledge_base is None:
            return Response({"detail": "Knowledge base non disponibile."}, status=status.HTTP_404_NOT_FOUND)
        serializer = KnowledgeSearchSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        try:
            with transaction.atomic():
                run, created = Run.objects.get_or_create(
                    workspace=request.workspace, source_product="ai_labs_retrieval",
                    idempotency_key=data["idempotency_key"],
                    defaults={
                        "kind": Run.RETRIEVAL, "created_by": request.user, "status": Run.RUNNING,
                        "started_at": timezone.now(), "input": {"knowledge_base_id": knowledge_base.pk, "query": data["query"]},
                    },
                )
        except IntegrityError:
            run = Run.objects.get(
                workspace=request.workspace, source_product="ai_labs_retrieval", idempotency_key=data["idempotency_key"],
            )
            created = False
        if not created:
            if run.input != {"knowledge_base_id": knowledge_base.pk, "query": data["query"]}:
                return Response({"detail": "Chiave di idempotenza già usata."}, status=status.HTTP_400_BAD_REQUEST)
            return Response({"run": RunSerializer(run).data, "results": run.output.get("results", [])})
        try:
            results = search_knowledge_base(
                knowledge_base=knowledge_base, user=request.user, query=data["query"], limit=data["limit"], run=run,
            )
            run.output = {"results": results}
            run.status = Run.COMPLETED
            run.ended_at = timezone.now()
            run.save(update_fields=("output", "status", "ended_at", "updated_at"))
        except Exception as exc:
            run.status = Run.FAILED
            run.error_code = type(exc).__name__
            run.error_message = str(exc)[:2000]
            run.ended_at = timezone.now()
            run.save(update_fields=("status", "error_code", "error_message", "ended_at", "updated_at"))
            raise
        return Response({"run": RunSerializer(run).data, "results": results})


class KnowledgeSourceViewSet(viewsets.ModelViewSet):
    serializer_class = KnowledgeSourceSerializer
    permission_classes = (IsAuthenticated, HasManagedWorkspace)

    def get_queryset(self):
        return KnowledgeSource.objects.filter(
            knowledge_base__workspace=self.request.workspace,
        ).select_related("knowledge_base", "created_by").prefetch_related("revisions__chunks").order_by("title")

    def perform_create(self, serializer):
        knowledge_base = KnowledgeBase.objects.filter(
            pk=self.request.data.get("knowledge_base"), workspace=self.request.workspace,
        ).first()
        if knowledge_base is None:
            raise PermissionDenied("Knowledge base non disponibile nel workspace.")
        serializer.save(knowledge_base=knowledge_base, created_by=self.request.user)

    @action(detail=True, methods=("post",))
    def ingest(self, request, pk=None):
        revision = create_revision(self.get_object())
        index_revision_task.delay(revision.pk)
        return Response({"revision_id": revision.pk, "status": revision.status}, status=status.HTTP_202_ACCEPTED)
