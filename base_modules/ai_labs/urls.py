from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    AgentRunCreateView, AgentViewSet, AiModelViewSet, AiProviderViewSet, ApprovalDecisionView, FlowRunCreateView,
    FlowViewSet, KnowledgeBaseViewSet, KnowledgeSourceViewSet, PublishedFlowListView, RunViewSet,
    ToolDefinitionViewSet, WorkspaceAiPolicyView,
)


router = DefaultRouter()
router.register("providers", AiProviderViewSet, basename="ai-provider")
router.register("models", AiModelViewSet, basename="ai-model")
router.register("tools", ToolDefinitionViewSet, basename="ai-tool")
router.register("agents", AgentViewSet, basename="ai-agent")
router.register("flows", FlowViewSet, basename="ai-flow")
router.register("runs", RunViewSet, basename="ai-run")
router.register("knowledge-bases", KnowledgeBaseViewSet, basename="ai-knowledge-base")
router.register("knowledge-sources", KnowledgeSourceViewSet, basename="ai-knowledge-source")

urlpatterns = [
    path("", include(router.urls)),
    path("workspace-policy/", WorkspaceAiPolicyView.as_view(), name="ai-workspace-policy"),
    path("published-flows/", PublishedFlowListView.as_view(), name="ai-published-flows"),
    path("published-flows/<int:flow_id>/runs/", FlowRunCreateView.as_view(), name="ai-flow-run"),
    path("published-agents/<int:agent_id>/runs/", AgentRunCreateView.as_view(), name="ai-agent-run"),
    path("approvals/<int:approval_id>/decision/", ApprovalDecisionView.as_view(), name="ai-approval-decision"),
]
