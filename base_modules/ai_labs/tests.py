from decimal import Decimal
from unittest.mock import Mock, patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import connection, connections
from django.test import TestCase, TransactionTestCase
from concurrent.futures import ThreadPoolExecutor
from rest_framework.test import APIClient

from base_modules.user_manager.models import User
from base_modules.workspace.models import Workspace, WorkspaceUser

from .models import (
    Agent, AiModel, AiProvider, ApprovalRequest, Flow, KnowledgeBase, KnowledgeChunk,
    KnowledgeRevision, KnowledgeSource, Run, ToolDefinition, WorkspaceAiPolicy,
)
from .providers import ProviderResult
from .accounting import reserve_budget
from .knowledge import search_knowledge_base
from .registry import ToolContract, register_tool
from .services import decide_approval, execute_run, publish_agent, publish_flow, start_agent_run, start_flow_run


class AiLabsRuntimeTests(TestCase):
    def setUp(self):
        self.workspace = Workspace.objects.create(workspace_name="AI")
        self.other_workspace = Workspace.objects.create(workspace_name="Other")
        self.owner = User.objects.create_user("owner", "owner@example.test")
        self.member = User.objects.create_user("member", "member@example.test")
        self.foreign = User.objects.create_user("foreign", "foreign@example.test")
        WorkspaceUser.objects.create(user=self.owner, workspace=self.workspace, role=WorkspaceUser.OWNER)
        WorkspaceUser.objects.create(user=self.member, workspace=self.workspace)
        WorkspaceUser.objects.create(user=self.foreign, workspace=self.other_workspace, role=WorkspaceUser.OWNER)
        self.provider = AiProvider.objects.create(
            name="Regolo", kind=AiProvider.REGOLO, base_url="https://api.example.test/v1",
        )
        self.model = AiModel.objects.create(
            provider=self.provider, model_id="test-model", display_name="Test",
            capabilities=["chat"], prompt_cost_per_million=Decimal("2.0"),
            completion_cost_per_million=Decimal("4.0"),
        )

    def flow(self, graph, input_schema=None, output_schema=None):
        flow = Flow.objects.create(
            workspace=self.workspace, name="Flow", slug=f"flow-{Flow.objects.count()}", created_by=self.owner,
            draft_graph=graph, draft_input_schema=input_schema or {}, draft_output_schema=output_schema or {},
        )
        publish_flow(flow=flow, actor=self.owner)
        flow.refresh_from_db()
        return flow

    def test_llm_run_is_versioned_traced_and_accounted(self):
        flow = self.flow({
            "nodes": [
                {"id": "start", "type": "input", "config": {}},
                {"id": "generate", "type": "llm", "config": {
                    "model_id": self.model.pk, "max_output_tokens": 20,
                    "messages": [{"role": "user", "content": "Hello {{ input.name }}"}],
                }},
                {"id": "finish", "type": "output", "config": {"value": "{{ nodes.generate.message.content }}"}},
            ],
            "edges": [{"from": "start", "to": "generate"}, {"from": "generate", "to": "finish"}],
            "output": "finish",
        }, input_schema={"type": "object", "required": ["name"], "properties": {"name": {"type": "string"}}},
           output_schema={"type": "string"})
        run, created = start_flow_run(
            flow=flow, actor=self.member, input_data={"name": "Ada"}, idempotency_key="request-1",
        )
        self.assertTrue(created)
        fake = Mock()
        fake.complete.return_value = ProviderResult(
            output={"message": {"role": "assistant", "content": "Ciao"}, "finish_reason": "stop"},
            prompt_tokens=5, completion_tokens=3, total_tokens=8, latency_ms=12,
        )
        with patch("base_modules.ai_labs.services.client_for_model", return_value=fake):
            execute_run(run.pk)
        run.refresh_from_db()
        self.assertEqual(run.status, Run.COMPLETED)
        self.assertEqual(run.output, {"result": "Ciao"})
        self.assertEqual((run.prompt_tokens, run.completion_tokens, run.total_tokens), (5, 3, 8))
        self.assertEqual(run.cost_microunits, 22)
        self.assertIsNone(run.events.get(event_type="model.completed").debug_content)
        self.assertNotIn("Hello Ada", str(run.events.get(event_type="model.completed").metadata))
        repeated, was_created = start_flow_run(
            flow=flow, actor=self.member, input_data={"name": "Ada"}, idempotency_key="request-1",
        )
        self.assertFalse(was_created)
        self.assertEqual(repeated.pk, run.pk)
        with self.assertRaisesMessage(Exception, "idempotenza"):
            start_flow_run(flow=flow, actor=self.member, input_data={"name": "Bob"}, idempotency_key="request-1")

    def test_budget_blocks_before_provider_call_and_unknown_prices_fail_closed(self):
        WorkspaceAiPolicy.objects.create(workspace=self.workspace, monthly_token_budget=5, max_run_tokens=100)
        flow = self.flow({
            "nodes": [{"id": "generate", "type": "llm", "config": {
                "model_id": self.model.pk, "max_output_tokens": 10,
                "messages": [{"role": "user", "content": "budget"}],
            }}], "edges": [], "output": "generate",
        })
        run, _ = start_flow_run(flow=flow, actor=self.member, input_data={}, idempotency_key="budget")
        fake = Mock()
        with patch("base_modules.ai_labs.services.client_for_model", return_value=fake):
            execute_run(run.pk)
        run.refresh_from_db()
        self.assertEqual(run.status, Run.FAILED)
        self.assertIn("Budget token", run.error_message)
        fake.complete.assert_not_called()

        policy = WorkspaceAiPolicy.objects.get(workspace=self.workspace)
        policy.monthly_token_budget = None
        policy.monthly_budget_microunits = 100
        policy.save()
        self.model.prompt_cost_per_million = None
        self.model.save(update_fields=("prompt_cost_per_million",))
        run, _ = start_flow_run(flow=flow, actor=self.member, input_data={}, idempotency_key="unknown-cost")
        with patch("base_modules.ai_labs.services.client_for_model", return_value=fake):
            execute_run(run.pk)
        run.refresh_from_db()
        self.assertIn("Costo non stimabile", run.error_message)
        fake.complete.assert_not_called()

    def test_tool_approval_pauses_and_resumes_same_request(self):
        calls = []

        def handler(**kwargs):
            calls.append(kwargs["input_data"])
            return {"accepted": kwargs["input_data"]["value"]}

        register_tool(ToolContract(
            key="tests.approved", handler=handler,
            input_schema={"type": "object", "required": ["value"], "properties": {"value": {"type": "integer"}}},
            output_schema={"type": "object", "required": ["accepted"], "properties": {"accepted": {"type": "integer"}}},
            side_effect=True,
        ))
        ToolDefinition.objects.create(workspace=self.workspace, key="tests.approved", name="Approved", side_effect=True)
        flow = self.flow({
            "nodes": [
                {"id": "action", "type": "tool", "config": {"tool": "tests.approved", "input": {"value": 7}}},
                {"id": "finish", "type": "output", "config": {"value": "{{ nodes.action }}"}},
            ],
            "edges": [{"from": "action", "to": "finish"}], "output": "finish",
        })
        run, _ = start_flow_run(flow=flow, actor=self.member, input_data={}, idempotency_key="approval")
        execute_run(run.pk)
        run.refresh_from_db()
        self.assertEqual(run.status, Run.AWAITING_APPROVAL)
        self.assertEqual(calls, [])
        approval = run.approvals.get()
        decide_approval(approval=approval, actor=self.owner, approve=True)
        execute_run(run.pk)
        run.refresh_from_db()
        self.assertEqual(run.status, Run.COMPLETED)
        self.assertEqual(run.output, {"accepted": 7})
        self.assertEqual(calls, [{"value": 7}])

    def test_graph_rejects_cycles_and_invalid_area_style_fallbacks_are_not_part_of_runtime(self):
        flow = Flow.objects.create(
            workspace=self.workspace, name="Invalid", slug="invalid", created_by=self.owner,
            draft_graph={
                "nodes": [{"id": "a", "type": "input", "config": {}}, {"id": "b", "type": "output", "config": {}}],
                "edges": [{"from": "a", "to": "b"}, {"from": "b", "to": "a"}],
            },
        )
        with self.assertRaisesMessage(Exception, "ciclo"):
            publish_flow(flow=flow, actor=self.owner)

    def test_agent_executes_only_assigned_tool_and_keeps_same_trace(self):
        calls = []

        def handler(**kwargs):
            calls.append(kwargs["input_data"])
            return {"answer": 42}

        register_tool(ToolContract(
            key="tests.lookup", handler=handler,
            input_schema={"type": "object", "properties": {"query": {"type": "string"}}},
            output_schema={"type": "object", "properties": {"answer": {"type": "integer"}}},
        ))
        tool = ToolDefinition.objects.create(workspace=self.workspace, key="tests.lookup", name="Lookup")
        agent = Agent.objects.create(workspace=self.workspace, name="Helper", slug="helper", created_by=self.owner)
        publish_agent(
            agent=agent, actor=self.owner, model=self.model, system_prompt="Use tools.", tool_ids=[tool.pk],
            output_schema={"type": "object", "required": ["message"]},
        )
        agent.refresh_from_db()
        run, _ = start_agent_run(
            agent=agent, actor=self.member, input_data={"question": "value"}, idempotency_key="agent-1",
        )
        fake = Mock()
        fake.complete.side_effect = [
            ProviderResult(
                output={"message": {"role": "assistant", "content": None, "tool_calls": [{
                    "id": "call-1", "type": "function",
                    "function": {"name": "tests.lookup", "arguments": '{"query":"value"}'},
                }]}}, prompt_tokens=3, completion_tokens=2, total_tokens=5, latency_ms=4,
            ),
            ProviderResult(
                output={"message": {"role": "assistant", "content": "42"}},
                prompt_tokens=6, completion_tokens=1, total_tokens=7, latency_ms=4,
            ),
        ]
        with patch("base_modules.ai_labs.services.client_for_model", return_value=fake):
            execute_run(run.pk)
        run.refresh_from_db()
        self.assertEqual(run.status, Run.COMPLETED)
        self.assertEqual(run.output["message"]["content"], "42")
        self.assertEqual(calls, [{"query": "value"}])
        self.assertEqual(run.total_tokens, 12)

    def test_retrieval_revalidates_private_source_after_vector_search(self):
        self.model.capabilities = ["embedding"]
        self.model.save(update_fields=("capabilities",))
        kb = KnowledgeBase.objects.create(
            workspace=self.workspace, name="KB", slug="kb", embedding_model=self.model,
            vector_size=2, created_by=self.owner,
        )
        own_source = KnowledgeSource.objects.create(
            knowledge_base=kb, source_type=KnowledgeSource.UPLOAD, title="Own",
            visibility=KnowledgeSource.PRIVATE, created_by=self.member,
            uploaded_file=SimpleUploadedFile("own.txt", b"own"),
        )
        foreign_source = KnowledgeSource.objects.create(
            knowledge_base=kb, source_type=KnowledgeSource.UPLOAD, title="Foreign",
            visibility=KnowledgeSource.PRIVATE, created_by=self.owner,
            uploaded_file=SimpleUploadedFile("foreign.txt", b"foreign"),
        )
        own_revision = KnowledgeRevision.objects.create(
            source=own_source, version=1, checksum="a" * 64, status=KnowledgeRevision.READY,
            index_generation=kb.index_generation,
        )
        foreign_revision = KnowledgeRevision.objects.create(
            source=foreign_source, version=1, checksum="b" * 64, status=KnowledgeRevision.READY,
            index_generation=kb.index_generation,
        )
        own_chunk = KnowledgeChunk.objects.create(revision=own_revision, ordinal=0, text="allowed")
        foreign_chunk = KnowledgeChunk.objects.create(revision=foreign_revision, ordinal=0, text="denied")
        client = Mock()
        client.embed.return_value = ([[0.1, 0.2]], 2, 3)
        store = Mock()
        store.search.return_value = [
            {"id": str(foreign_chunk.vector_point_id), "score": 0.99},
            {"id": str(own_chunk.vector_point_id), "score": 0.80},
        ]
        with patch("base_modules.ai_labs.knowledge.client_for_model", return_value=client):
            results = search_knowledge_base(knowledge_base=kb, user=self.member, query="query", store=store)
        self.assertEqual([item["text"] for item in results], ["allowed"])
        self.assertEqual(results[0]["trust"], "untrusted_source")


class AiLabsApiTests(TestCase):
    def setUp(self):
        self.workspace = Workspace.objects.create(workspace_name="AI")
        self.other_workspace = Workspace.objects.create(workspace_name="Other")
        self.owner = User.objects.create_user("owner", "owner@example.test")
        self.member = User.objects.create_user("member", "member@example.test")
        self.foreign = User.objects.create_user("foreign", "foreign@example.test")
        self.admin = User.objects.create_superuser("admin", "admin@example.test", password="unused")
        WorkspaceUser.objects.create(user=self.owner, workspace=self.workspace, role=WorkspaceUser.OWNER)
        WorkspaceUser.objects.create(user=self.member, workspace=self.workspace)
        WorkspaceUser.objects.create(user=self.foreign, workspace=self.other_workspace, role=WorkspaceUser.OWNER)
        self.header = {"HTTP_X_WORKSPACE_ID": str(self.workspace.pk)}
        self.client = APIClient()

    def test_management_and_provider_boundaries(self):
        self.assertIn(self.client.get("/api/ai-labs/flows/", **self.header).status_code, (401, 403))
        self.client.force_authenticate(self.member)
        self.assertEqual(self.client.get("/api/ai-labs/flows/", **self.header).status_code, 403)
        self.client.force_authenticate(self.foreign)
        self.assertEqual(self.client.get("/api/ai-labs/flows/", **self.header).status_code, 403)
        self.client.force_authenticate(self.owner)
        response = self.client.post("/api/ai-labs/flows/", {
            "name": "Managed", "slug": "managed",
            "draft_graph": {"nodes": [{"id": "input", "type": "input", "config": {}}], "edges": []},
        }, format="json", **self.header)
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(self.client.patch("/api/ai-labs/workspace-policy/", {"monthly_token_budget": 100},
                                           format="json", **self.header).status_code, 403)
        self.assertEqual(self.client.post("/api/ai-labs/providers/", {
            "name": "Denied", "kind": "regolo", "base_url": "https://api.example.test/v1",
        }, format="json").status_code, 403)
        self.client.force_authenticate(self.admin)
        self.assertEqual(self.client.post("/api/ai-labs/providers/", {
            "name": "Allowed", "kind": "regolo", "base_url": "https://api.example.test/v1",
        }, format="json").status_code, 201)

    def test_member_starts_only_published_flow_in_own_workspace(self):
        flow = Flow.objects.create(
            workspace=self.workspace, name="Published", slug="published", created_by=self.owner,
            draft_graph={"nodes": [{"id": "input", "type": "input", "config": {}}], "edges": [], "output": "input"},
        )
        publish_flow(flow=flow, actor=self.owner)
        self.client.force_authenticate(self.member)
        with patch("base_modules.ai_labs.views.execute_run_task.delay") as enqueue:
            response = self.client.post(
                f"/api/ai-labs/published-flows/{flow.pk}/runs/",
                {"input": {"safe": True}, "idempotency_key": "api-1"}, format="json", **self.header,
            )
        self.assertEqual(response.status_code, 202, response.data)
        enqueue.assert_called_once()
        self.client.force_authenticate(self.foreign)
        self.assertEqual(self.client.post(
            f"/api/ai-labs/published-flows/{flow.pk}/runs/",
            {"input": {}, "idempotency_key": "foreign"}, format="json", **self.header,
        ).status_code, 403)


class BudgetConcurrencyTests(TransactionTestCase):
    reset_sequences = True

    def test_postgresql_serializes_competing_reservations(self):
        if connection.vendor != "postgresql":
            self.skipTest("La semantica select_for_update è verificata su PostgreSQL.")
        workspace = Workspace.objects.create(workspace_name="Concurrent")
        actor = User.objects.create_user("budget-user", "budget@example.test")
        WorkspaceUser.objects.create(workspace=workspace, user=actor)
        provider = AiProvider.objects.create(name="Budget", kind=AiProvider.REGOLO, base_url="https://example.test")
        AiModel.objects.create(provider=provider, model_id="budget", display_name="Budget")
        flow = Flow.objects.create(
            workspace=workspace, name="Budget", slug="budget", created_by=actor,
            draft_graph={"nodes": [{"id": "input", "type": "input", "config": {}}], "edges": [], "output": "input"},
        )
        publish_flow(flow=flow, actor=actor)
        flow.refresh_from_db()
        WorkspaceAiPolicy.objects.create(workspace=workspace, monthly_token_budget=10, max_run_tokens=10)
        runs = [Run.objects.create(
            kind=Run.FLOW, workspace=workspace, flow_version=flow.published_version, created_by=actor,
            source_product="tests", idempotency_key=f"concurrent-{index}",
        ) for index in range(2)]

        def reserve(run_id):
            try:
                run = Run.objects.select_related("workspace").get(pk=run_id)
                reserve_budget(run=run, key="call", estimated_tokens=8, estimated_cost_microunits=1)
                return "accepted"
            except Exception:
                return "blocked"
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as executor:
            outcomes = list(executor.map(reserve, [run.pk for run in runs]))
        self.assertEqual(sorted(outcomes), ["accepted", "blocked"])
