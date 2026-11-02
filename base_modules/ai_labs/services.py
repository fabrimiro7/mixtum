import hashlib
import json
import re
from datetime import timedelta

from django.db import IntegrityError, models, transaction
from django.db.models import F, Max, Sum
from django.db.models.functions import Coalesce
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError

from .accounting import reconcile_budget, release_budget, reserve_budget
from .graph import edge_is_active, incoming_edges, resolve_value, validate_graph
from .models import (
    Agent, AgentVersion, ApprovalRequest, Flow, FlowVersion, Run, RunEvent, ToolDefinition, WorkspaceAiPolicy,
)
from .providers import client_for_model, estimate_cost_microunits, estimate_tokens
from .redaction import redact
from .registry import get_node, get_tool, notify_run_completed
from .schema import validate_schema, value_at_path


def _assert_execution_identity(*, user, workspace):
    from base_modules.workspace.models import WorkspaceUser

    if not user.is_active or not WorkspaceUser.objects.filter(user=user, workspace=workspace).exists():
        raise PermissionDenied("L'identità esecutiva non appartiene più al workspace.")


def _event(run, event_type, *, node_id="", metadata=None, debug_content=None):
    sequence = (run.events.aggregate(value=Max("sequence"))["value"] or 0) + 1
    policy, _ = WorkspaceAiPolicy.objects.get_or_create(workspace=run.workspace)
    debug_allowed = bool(policy.debug_enabled_until and policy.debug_enabled_until > timezone.now())
    return RunEvent.objects.create(
        run=run, sequence=sequence, event_type=event_type, node_id=node_id,
        metadata=redact(metadata or {}),
        debug_content=redact(debug_content) if debug_allowed and debug_content is not None else None,
        debug_expires_at=(timezone.now() + timedelta(days=policy.debug_retention_days))
        if debug_allowed and debug_content is not None else None,
    )


@transaction.atomic
def publish_flow(*, flow, actor):
    flow = Flow.objects.select_for_update().get(pk=flow.pk, workspace=flow.workspace)
    validate_graph(flow.draft_graph)
    number = (flow.versions.aggregate(value=Max("version"))["value"] or 0) + 1
    version = FlowVersion.objects.create(
        flow=flow, version=number, graph=flow.draft_graph,
        input_schema=flow.draft_input_schema, output_schema=flow.draft_output_schema, created_by=actor,
    )
    flow.published_version = version
    flow.save(update_fields=("published_version", "updated_at"))
    return version


@transaction.atomic
def publish_agent(*, agent, actor, model, system_prompt, input_schema=None, output_schema=None, config=None, tool_ids=None):
    agent = Agent.objects.select_for_update().get(pk=agent.pk, workspace=agent.workspace)
    if not model.enabled or not model.provider.enabled:
        raise ValidationError("Modello AI non disponibile.")
    number = (agent.versions.aggregate(value=Max("version"))["value"] or 0) + 1
    version = AgentVersion.objects.create(
        agent=agent, version=number, model=model, system_prompt=system_prompt,
        input_schema=input_schema or {}, output_schema=output_schema or {}, config=config or {}, created_by=actor,
    )
    tools = list(ToolDefinition.objects.filter(pk__in=tool_ids or []).filter(
        models.Q(workspace=agent.workspace) | models.Q(workspace__isnull=True)
    )) if tool_ids else []
    if len(tools) != len(set(tool_ids or [])):
        raise ValidationError("Tool non disponibile nel workspace.")
    for order, tool in enumerate(tools):
        version.tool_assignments.create(tool=tool, order=order)
    agent.published_version = version
    agent.save(update_fields=("published_version", "updated_at"))
    return version


def start_flow_run(*, flow, actor, input_data, idempotency_key, source_product="ai_labs"):
    _assert_execution_identity(user=actor, workspace=flow.workspace)
    if flow.published_version_id is None:
        raise ValidationError("Il flow non è pubblicato.")
    if not re.fullmatch(r"[a-z][a-z0-9_-]{0,79}", source_product):
        raise ValidationError("Prodotto sorgente non valido.")
    if not idempotency_key or len(idempotency_key) > 160:
        raise ValidationError("Chiave di idempotenza obbligatoria e non valida.")
    validate_schema(flow.published_version.input_schema, input_data)
    try:
        with transaction.atomic():
            run, created = Run.objects.get_or_create(
                workspace=flow.workspace, source_product=source_product, idempotency_key=idempotency_key,
                defaults={"flow_version": flow.published_version, "created_by": actor, "input": input_data},
            )
    except IntegrityError:
        run = Run.objects.get(
            workspace=flow.workspace, source_product=source_product, idempotency_key=idempotency_key,
        )
        created = False
    if not created and (run.flow_version_id != flow.published_version_id or run.input != input_data):
        raise ValidationError("Chiave di idempotenza già usata con una richiesta diversa.")
    if created:
        _event(run, "run.created", metadata={"source_product": source_product, "flow_version": flow.published_version.version})
    return run, created


def start_agent_run(*, agent, actor, input_data, idempotency_key, source_product="ai_labs"):
    _assert_execution_identity(user=actor, workspace=agent.workspace)
    if agent.published_version_id is None:
        raise ValidationError("L'agente non è pubblicato.")
    if not re.fullmatch(r"[a-z][a-z0-9_-]{0,79}", source_product):
        raise ValidationError("Prodotto sorgente non valido.")
    if not idempotency_key or len(idempotency_key) > 160:
        raise ValidationError("Chiave di idempotenza obbligatoria e non valida.")
    validate_schema(agent.published_version.input_schema, input_data)
    try:
        with transaction.atomic():
            run, created = Run.objects.get_or_create(
                workspace=agent.workspace, source_product=source_product, idempotency_key=idempotency_key,
                defaults={
                    "kind": Run.AGENT, "agent_version": agent.published_version,
                    "created_by": actor, "input": input_data,
                },
            )
    except IntegrityError:
        run = Run.objects.get(workspace=agent.workspace, source_product=source_product, idempotency_key=idempotency_key)
        created = False
    if not created and (run.agent_version_id != agent.published_version_id or run.input != input_data):
        raise ValidationError("Chiave di idempotenza già usata con una richiesta diversa.")
    if created:
        _event(run, "run.created", metadata={"source_product": source_product, "agent_version": agent.published_version.version})
    return run, created


def _messages_for_node(node, context):
    config = node.get("config", {})
    messages = resolve_value(config.get("messages", []), context)
    if not isinstance(messages, list) or not all(
        isinstance(item, dict) and item.get("role") in {"system", "user", "assistant"}
        and isinstance(item.get("content"), str) for item in messages
    ):
        raise ValidationError(f"Messaggi non validi nel nodo {node['id']}.")
    return messages


def _run_llm_node(run, node, context):
    from .models import AiModel

    config = node.get("config", {})
    completed_models = (run.state or {}).get("completed_models", {})
    if node["id"] in completed_models:
        return completed_models[node["id"]]
    if node["id"] in (run.state or {}).get("model_in_flight", []):
        raise ValidationError("Esito della precedente chiamata modello incerto; ripetizione automatica bloccata.")
    model = AiModel.objects.select_related("provider").filter(
        pk=config.get("model_id"), enabled=True, provider__enabled=True,
    ).first()
    if model is None:
        raise ValidationError(f"Modello non disponibile nel nodo {node['id']}.")
    messages = _messages_for_node(node, context)
    max_output = min(max(int(config.get("max_output_tokens", 1024)), 1), 32768)
    estimated_prompt = max(1, estimate_tokens(messages, 0))
    reservation = reserve_budget(
        run=run, key=f"node:{node['id']}", estimated_tokens=estimated_prompt + max_output,
        estimated_cost_microunits=estimate_cost_microunits(model, estimated_prompt, max_output),
    )
    _event(run, "model.started", node_id=node["id"], metadata={"provider": model.provider.name, "model": model.model_id})
    run.state = {
        **(run.state or {}),
        "model_in_flight": sorted(set((run.state or {}).get("model_in_flight", [])) | {node["id"]}),
    }
    run.save(update_fields=("state", "updated_at"))
    sent = False
    try:
        sent = True
        result = client_for_model(model).complete(model=model, messages=messages, max_output_tokens=max_output)
    except Exception:
        if not sent:
            release_budget(reservation)
        else:
            reconcile_budget(reservation, actual_tokens=None, actual_cost_microunits=None)
        raise
    cost = estimate_cost_microunits(model, result.prompt_tokens, result.completion_tokens) \
        if result.prompt_tokens is not None and result.completion_tokens is not None else None
    reconcile_budget(reservation, actual_tokens=result.total_tokens, actual_cost_microunits=cost)
    run.prompt_tokens = (run.prompt_tokens or 0) + result.prompt_tokens if result.prompt_tokens is not None else run.prompt_tokens
    run.completion_tokens = ((run.completion_tokens or 0) + result.completion_tokens
                             if result.completion_tokens is not None else run.completion_tokens)
    run.save(update_fields=("prompt_tokens", "completion_tokens", "updated_at"))
    in_flight = set((run.state or {}).get("model_in_flight", []))
    in_flight.discard(node["id"])
    run.state = {
        **(run.state or {}), "model_in_flight": sorted(in_flight),
        "completed_models": {**completed_models, node["id"]: result.output},
    }
    run.save(update_fields=("state", "updated_at"))
    _event(
        run, "model.completed", node_id=node["id"],
        metadata={
            "provider": model.provider.name, "model": model.model_id, "latency_ms": result.latency_ms,
            "prompt_tokens": result.prompt_tokens, "completion_tokens": result.completion_tokens,
            "total_tokens": result.total_tokens, "cost_microunits": cost,
        },
        debug_content={"messages": messages, "output": result.output},
    )
    return result.output


def _tool_fingerprint(key, payload):
    return hashlib.sha256(json.dumps({"tool": key, "input": payload}, sort_keys=True, default=str).encode()).hexdigest()


def _run_tool_node(run, node, context):
    config = node.get("config", {})
    key = str(config.get("tool", ""))
    contract = get_tool(key)
    definition = ToolDefinition.objects.filter(key=key, enabled=True).filter(
        models.Q(workspace=run.workspace) | models.Q(workspace__isnull=True)
    ).order_by(models.F("workspace").desc(nulls_last=True)).first()
    if definition is None:
        raise ValidationError(f"Tool non disponibile: {key}.")
    if contract.permission and not run.created_by.has_perm(contract.permission):
        raise PermissionDenied(f"Permesso tool mancante: {contract.permission}.")
    payload = resolve_value(config.get("input", {}), context)
    validate_schema(contract.input_schema or definition.input_schema, payload, path="tool_input")
    fingerprint = _tool_fingerprint(key, payload)
    completed_tools = (run.state or {}).get("completed_tools", {})
    if node["id"] in completed_tools:
        completed = completed_tools[node["id"]]
        if completed.get("fingerprint") != fingerprint:
            raise ValidationError("La richiesta tool è cambiata dopo l'esecuzione.")
        return completed["result"]
    requires_approval = contract.requires_approval or contract.side_effect or definition.requires_approval or definition.side_effect
    if requires_approval:
        approval, _ = ApprovalRequest.objects.get_or_create(
            run=run, node_id=node["id"],
            defaults={"request_fingerprint": fingerprint, "payload": redact(payload)},
        )
        if approval.request_fingerprint != fingerprint:
            raise ValidationError("La richiesta tool è cambiata dopo l'approvazione.")
        if approval.status == ApprovalRequest.PENDING:
            run.status = Run.AWAITING_APPROVAL
            run.state = {**run.state, "waiting_node": node["id"]}
            run.save(update_fields=("status", "state", "updated_at"))
            _event(run, "approval.requested", node_id=node["id"], metadata={"tool": key})
            return None
        if approval.status == ApprovalRequest.REJECTED:
            raise PermissionDenied("Esecuzione tool rifiutata.")
    _event(run, "tool.started", node_id=node["id"], metadata={"tool": key})
    result = contract.handler(actor=run.created_by, workspace=run.workspace, input_data=payload, run=run)
    validate_schema(contract.output_schema or definition.output_schema, result, path="tool_output")
    run.state = {
        **(run.state or {}),
        "completed_tools": {
            **completed_tools,
            node["id"]: {"fingerprint": fingerprint, "result": result},
        },
    }
    run.save(update_fields=("state", "updated_at"))
    _event(run, "tool.completed", node_id=node["id"], metadata={"tool": key}, debug_content={"input": payload, "output": result})
    return result


def _agent_tools(agent_version):
    result = []
    for assignment in agent_version.tool_assignments.select_related("tool").order_by("order"):
        tool = assignment.tool
        result.append({
            "type": "function",
            "function": {"name": tool.key, "description": tool.description, "parameters": tool.input_schema or {"type": "object"}},
        })
    return result


def _run_agent(run):
    version = run.agent_version
    max_steps = min(max(int(version.config.get("max_steps", 8)), 1), 50)
    state = dict(run.state or {})
    messages = state.get("messages") or [
        {"role": "system", "content": version.system_prompt},
        {"role": "user", "content": json.dumps(run.input, ensure_ascii=False)},
    ]
    step = int(state.get("step", 0))
    tools = _agent_tools(version)
    assigned = {item["function"]["name"] for item in tools}
    while step < max_steps:
        _assert_execution_identity(user=run.created_by, workspace=run.workspace)
        pending = state.get("pending_tool")
        if pending:
            if pending["name"] not in assigned:
                raise PermissionDenied("Il modello ha richiesto un tool non assegnato.")
            node = {"id": pending["node_id"], "type": "tool", "config": {"tool": pending["name"], "input": pending["arguments"]}}
            result = _run_tool_node(run, node, {"input": run.input, "nodes": {}})
            run.refresh_from_db(fields=("status", "state"))
            if run.status == Run.AWAITING_APPROVAL:
                run.state = {**run.state, "messages": messages, "step": step, "pending_tool": pending}
                run.save(update_fields=("state", "updated_at"))
                return None
            messages.append({"role": "tool", "tool_call_id": pending["call_id"], "content": json.dumps(result, ensure_ascii=False)})
            state = {**run.state, "messages": messages, "step": step + 1}
            state.pop("pending_tool", None)
            run.state = state
            run.save(update_fields=("state", "updated_at"))
            step += 1
            continue
        max_output = min(max(int(version.config.get("max_output_tokens", 1024)), 1), 32768)
        estimated_prompt = estimate_tokens(messages, 0)
        reservation = reserve_budget(
            run=run, key=f"agent:model:{step}", estimated_tokens=estimated_prompt + max_output,
            estimated_cost_microunits=estimate_cost_microunits(version.model, estimated_prompt, max_output),
        )
        _event(run, "model.started", node_id=f"agent-{step}", metadata={"model": version.model.model_id})
        result = client_for_model(version.model).complete(
            model=version.model, messages=messages, max_output_tokens=max_output, tools=tools or None,
        )
        cost = estimate_cost_microunits(version.model, result.prompt_tokens, result.completion_tokens) \
            if result.prompt_tokens is not None and result.completion_tokens is not None else None
        reconcile_budget(reservation, actual_tokens=result.total_tokens, actual_cost_microunits=cost)
        if result.prompt_tokens is not None:
            run.prompt_tokens = (run.prompt_tokens or 0) + result.prompt_tokens
        if result.completion_tokens is not None:
            run.completion_tokens = (run.completion_tokens or 0) + result.completion_tokens
        run.save(update_fields=("prompt_tokens", "completion_tokens", "updated_at"))
        message = result.output.get("message") or {}
        _event(run, "model.completed", node_id=f"agent-{step}", metadata={
            "model": version.model.model_id, "latency_ms": result.latency_ms,
            "prompt_tokens": result.prompt_tokens, "completion_tokens": result.completion_tokens,
        }, debug_content={"messages": messages, "output": result.output})
        tool_calls = message.get("tool_calls") or []
        if tool_calls:
            if len(tool_calls) != 1:
                raise ValidationError("Una risposta agente può richiedere un solo tool per passo.")
            call = tool_calls[0]
            function = call.get("function") or {}
            try:
                arguments = json.loads(function.get("arguments") or "{}")
            except json.JSONDecodeError as exc:
                raise ValidationError("Argomenti tool prodotti dal modello non validi.") from exc
            name = function.get("name", "")
            if name not in assigned:
                raise PermissionDenied("Il modello ha richiesto un tool non assegnato.")
            messages.append(message)
            safe_call_id = re.sub(r"[^a-zA-Z0-9_-]", "-", str(call.get("id", step)))[:80]
            state = {**run.state, "messages": messages, "step": step, "pending_tool": {
                "call_id": str(call.get("id", step)), "node_id": f"agent-tool-{step}-{safe_call_id}",
                "name": name, "arguments": arguments,
            }}
            run.state = state
            run.save(update_fields=("state", "updated_at"))
            continue
        content = message.get("content")
        output = {"message": message}
        if version.config.get("parse_json"):
            try:
                output = json.loads(content)
            except (TypeError, json.JSONDecodeError) as exc:
                raise ValidationError("Output JSON dell'agente non valido.") from exc
        validate_schema(version.output_schema, output, path="output")
        return output
    raise ValidationError("Limite massimo di passi agente raggiunto.")


def _execute_node(run, node, context, predecessors):
    node_type = node["type"]
    config = node.get("config", {})
    if node_type == "input":
        return run.input
    if node_type == "llm":
        return _run_llm_node(run, node, context)
    if node_type == "condition":
        left = resolve_value(config.get("value"), context)
        operator = config.get("operator", "truthy")
        right = resolve_value(config.get("compare"), context)
        operations = {
            "truthy": lambda: bool(left), "equals": lambda: left == right,
            "not_equals": lambda: left != right, "contains": lambda: right in left,
        }
        if operator not in operations:
            raise ValidationError(f"Operatore condizione non supportato: {operator}.")
        return operations[operator]()
    if node_type == "merge":
        return {node_id: context["nodes"].get(node_id) for node_id in predecessors}
    if node_type == "validate_json":
        value = resolve_value(config.get("value"), context)
        validate_schema(config.get("schema", {}), value, path=f"node.{node['id']}")
        return value
    if node_type == "tool":
        return _run_tool_node(run, node, context)
    if node_type == "retrieval":
        from .knowledge import search_knowledge_base
        from .models import KnowledgeBase

        knowledge_base = KnowledgeBase.objects.select_related("embedding_model__provider").filter(
            pk=config.get("knowledge_base_id"), workspace=run.workspace,
        ).first()
        if knowledge_base is None:
            raise ValidationError("Knowledge base non disponibile nel workspace.")
        query = resolve_value(config.get("query"), context)
        if not isinstance(query, str):
            raise ValidationError("Query retrieval non valida.")
        return search_knowledge_base(
            knowledge_base=knowledge_base, user=run.created_by, query=query,
            limit=int(config.get("limit", 8)), run=run, reservation_key=f"node:{node['id']}:embedding",
        )
    if node_type == "output":
        return resolve_value(config.get("value", "{{ input }}"), context)
    return get_node(node_type).executor(run=run, node=node, context=context, predecessors=predecessors)


def execute_run(run_id):
    run = Run.objects.select_related(
        "workspace", "created_by", "flow_version", "agent_version__model__provider",
    ).prefetch_related("agent_version__tool_assignments__tool").get(pk=run_id)
    if run.status in {Run.COMPLETED, Run.CANCELLED}:
        return run
    if run.status == Run.AWAITING_APPROVAL and run.approvals.filter(status=ApprovalRequest.PENDING).exists():
        return run
    run.status = Run.RUNNING
    run.started_at = run.started_at or timezone.now()
    run.save(update_fields=("status", "started_at", "updated_at"))
    _event(run, "run.started")
    if run.kind == Run.AGENT:
        try:
            output = _run_agent(run)
            run.refresh_from_db()
            if run.status == Run.AWAITING_APPROVAL:
                return run
            run.output = output or {}
            run.status = Run.COMPLETED
            run.ended_at = timezone.now()
            totals = run.budget_reservations.exclude(status="released").aggregate(
                tokens=Sum(Coalesce(F("actual_tokens"), F("estimated_tokens"))),
                cost=Sum(Coalesce(F("actual_cost_microunits"), F("estimated_cost_microunits"))),
            )
            run.total_tokens, run.cost_microunits = totals["tokens"], totals["cost"]
            run.save(update_fields=("output", "status", "ended_at", "total_tokens", "cost_microunits", "updated_at"))
            _event(run, "run.completed", metadata={"total_tokens": run.total_tokens, "cost_microunits": run.cost_microunits})
            notify_run_completed(run)
        except Exception as exc:
            run.status = Run.FAILED
            run.error_code = type(exc).__name__
            run.error_message = str(exc)[:2000]
            run.ended_at = timezone.now()
            run.save(update_fields=("status", "error_code", "error_message", "ended_at", "updated_at"))
            _event(run, "run.failed", metadata={"error_code": run.error_code, "message": run.error_message})
        return run
    if run.kind != Run.FLOW:
        return run
    graph = run.flow_version.graph
    order = validate_graph(graph)
    nodes = {node["id"]: node for node in graph["nodes"]}
    outputs = dict((run.state or {}).get("outputs", {}))
    skipped = set((run.state or {}).get("skipped", []))
    try:
        for node_id in order:
            if node_id in outputs or node_id in skipped:
                continue
            if Run.objects.filter(pk=run.pk, status=Run.CANCELLED).exists():
                return Run.objects.get(pk=run.pk)
            _assert_execution_identity(user=run.created_by, workspace=run.workspace)
            incoming = incoming_edges(graph, node_id)
            if incoming and not any(edge_is_active(edge, outputs) and edge["from"] not in skipped for edge in incoming):
                skipped.add(node_id)
                continue
            predecessors = [edge["from"] for edge in incoming if edge["from"] not in skipped]
            context = {"input": run.input, "nodes": outputs}
            _event(run, "node.started", node_id=node_id, metadata={"type": nodes[node_id]["type"]})
            result = _execute_node(run, nodes[node_id], context, predecessors)
            run.refresh_from_db(fields=("status", "state"))
            if run.status == Run.AWAITING_APPROVAL:
                run.state = {**run.state, "outputs": outputs, "skipped": sorted(skipped)}
                run.save(update_fields=("state", "updated_at"))
                return run
            outputs[node_id] = result
            run.state = {**(run.state or {}), "outputs": outputs, "skipped": sorted(skipped)}
            run.save(update_fields=("state", "updated_at"))
            _event(run, "node.completed", node_id=node_id, metadata={"type": nodes[node_id]["type"]})
        terminal = graph.get("output") or order[-1]
        output = outputs.get(terminal)
        validate_schema(run.flow_version.output_schema, output, path="output")
        totals = run.budget_reservations.exclude(status="released").aggregate(
            tokens=Sum(Coalesce(F("actual_tokens"), F("estimated_tokens"))),
            cost=Sum(Coalesce(F("actual_cost_microunits"), F("estimated_cost_microunits"))),
        )
        run.output = output if isinstance(output, dict) else {"result": output}
        run.status = Run.COMPLETED
        run.total_tokens = totals["tokens"]
        run.cost_microunits = totals["cost"]
        run.ended_at = timezone.now()
        run.save(update_fields=("output", "status", "total_tokens", "cost_microunits", "ended_at", "updated_at"))
        _event(run, "run.completed", metadata={"total_tokens": run.total_tokens, "cost_microunits": run.cost_microunits})
        notify_run_completed(run)
    except Exception as exc:
        run.status = Run.FAILED
        run.error_code = type(exc).__name__
        run.error_message = str(exc)[:2000]
        run.ended_at = timezone.now()
        run.save(update_fields=("status", "error_code", "error_message", "ended_at", "updated_at"))
        _event(run, "run.failed", metadata={"error_code": run.error_code, "message": run.error_message})
    return run


@transaction.atomic
def decide_approval(*, approval, actor, approve):
    approval = ApprovalRequest.objects.select_for_update().select_related("run__workspace").get(pk=approval.pk)
    if approval.status != ApprovalRequest.PENDING:
        raise ValidationError("Approvazione già decisa.")
    approval.status = ApprovalRequest.APPROVED if approve else ApprovalRequest.REJECTED
    approval.decided_by = actor
    approval.decided_at = timezone.now()
    approval.save(update_fields=("status", "decided_by", "decided_at"))
    approval.run.status = Run.PENDING if approve else Run.FAILED
    approval.run.error_code = "" if approve else "approval_rejected"
    approval.run.error_message = "" if approve else "Approvazione rifiutata."
    approval.run.save(update_fields=("status", "error_code", "error_message", "updated_at"))
    _event(approval.run, "approval.approved" if approve else "approval.rejected", node_id=approval.node_id)
    return approval.run
