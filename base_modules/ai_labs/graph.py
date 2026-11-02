import re
from collections import deque

from rest_framework.exceptions import ValidationError

from .registry import registered_nodes
from .schema import value_at_path


BUILTIN_NODE_TYPES = {"input", "llm", "condition", "merge", "validate_json", "tool", "retrieval", "output"}
_ID = re.compile(r"[a-z][a-z0-9_-]{0,119}")
_TEMPLATE = re.compile(r"{{\s*([a-zA-Z0-9_.-]+)\s*}}")


def validate_graph(graph):
    if not isinstance(graph, dict) or not isinstance(graph.get("nodes"), list) or not isinstance(graph.get("edges"), list):
        raise ValidationError({"graph": "Il grafo deve contenere liste nodes ed edges."})
    nodes = graph["nodes"]
    if not nodes or len(nodes) > 200:
        raise ValidationError({"graph": "Il grafo deve contenere da 1 a 200 nodi."})
    custom_types = {node.key for node in registered_nodes()}
    by_id = {}
    for node in nodes:
        if not isinstance(node, dict) or not _ID.fullmatch(str(node.get("id", ""))):
            raise ValidationError({"graph": "ID nodo non valido."})
        if node["id"] in by_id:
            raise ValidationError({"graph": f"Nodo duplicato: {node['id']}."})
        if node.get("type") not in BUILTIN_NODE_TYPES | custom_types:
            raise ValidationError({"graph": f"Tipo nodo non registrato: {node.get('type')}."})
        if not isinstance(node.get("config", {}), dict):
            raise ValidationError({"graph": f"Config nodo non valida: {node['id']}."})
        by_id[node["id"]] = node
    adjacency = {node_id: [] for node_id in by_id}
    indegree = {node_id: 0 for node_id in by_id}
    seen_edges = set()
    for edge in graph["edges"]:
        if not isinstance(edge, dict) or edge.get("from") not in by_id or edge.get("to") not in by_id:
            raise ValidationError({"graph": "Collegamento con nodo inesistente."})
        key = (edge["from"], edge["to"], str(edge.get("when", "")))
        if key in seen_edges:
            raise ValidationError({"graph": "Collegamento duplicato."})
        seen_edges.add(key)
        adjacency[edge["from"]].append(edge["to"])
        indegree[edge["to"]] += 1
    queue = deque(sorted(node_id for node_id, degree in indegree.items() if degree == 0))
    order = []
    while queue:
        node_id = queue.popleft()
        order.append(node_id)
        for target in adjacency[node_id]:
            indegree[target] -= 1
            if indegree[target] == 0:
                queue.append(target)
    if len(order) != len(by_id):
        raise ValidationError({"graph": "Il grafo contiene un ciclo libero."})
    entries = [node_id for node_id in order if not any(edge["to"] == node_id for edge in graph["edges"])]
    if graph.get("entry") and graph["entry"] not in entries:
        raise ValidationError({"graph": "Entry point non valido."})
    return order


def resolve_value(value, context):
    if isinstance(value, dict):
        return {key: resolve_value(item, context) for key, item in value.items()}
    if isinstance(value, list):
        return [resolve_value(item, context) for item in value]
    if not isinstance(value, str):
        return value
    match = _TEMPLATE.fullmatch(value)
    if match:
        return value_at_path(context, match.group(1))
    return _TEMPLATE.sub(lambda item: str(value_at_path(context, item.group(1))), value)


def incoming_edges(graph, node_id):
    return [edge for edge in graph["edges"] if edge["to"] == node_id]


def edge_is_active(edge, outputs):
    condition = edge.get("when")
    if condition is None:
        return True
    source = outputs.get(edge["from"])
    return bool(source) is bool(condition)
