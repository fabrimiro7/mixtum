from dataclasses import dataclass
from typing import Any, Callable

from django.core.exceptions import ImproperlyConfigured


@dataclass(frozen=True)
class ToolContract:
    key: str
    handler: Callable[..., dict]
    input_schema: dict
    output_schema: dict
    permission: str = ""
    side_effect: bool = False
    requires_approval: bool = False


@dataclass(frozen=True)
class NodeContract:
    key: str
    executor: Callable[..., Any]


@dataclass(frozen=True)
class SourceContract:
    key: str
    extract: Callable[..., list[dict]]
    can_access: Callable[..., bool]


_TOOLS: dict[str, ToolContract] = {}
_NODES: dict[str, NodeContract] = {}
_SOURCES: dict[str, SourceContract] = {}
_RUN_OBSERVERS: dict[str, Callable[..., None]] = {}


def register_tool(contract):
    if contract.key in _TOOLS and _TOOLS[contract.key] != contract:
        raise ImproperlyConfigured(f"Tool AI già registrato: {contract.key}")
    _TOOLS[contract.key] = contract


def get_tool(key):
    try:
        return _TOOLS[key]
    except KeyError as exc:
        raise ImproperlyConfigured(f"Tool AI non registrato: {key}") from exc


def registered_tools():
    return tuple(_TOOLS.values())


def register_node(contract):
    if contract.key in _NODES and _NODES[contract.key] != contract:
        raise ImproperlyConfigured(f"Nodo AI già registrato: {contract.key}")
    _NODES[contract.key] = contract


def get_node(key):
    try:
        return _NODES[key]
    except KeyError as exc:
        raise ImproperlyConfigured(f"Nodo AI non registrato: {key}") from exc


def registered_nodes():
    return tuple(_NODES.values())


def register_source(contract):
    if contract.key in _SOURCES and _SOURCES[contract.key] != contract:
        raise ImproperlyConfigured(f"Sorgente AI già registrata: {contract.key}")
    _SOURCES[contract.key] = contract


def get_source(key):
    try:
        return _SOURCES[key]
    except KeyError as exc:
        raise ImproperlyConfigured(f"Sorgente AI non registrata: {key}") from exc


def registered_sources():
    return tuple(_SOURCES.values())


def register_run_observer(key, handler):
    if key in _RUN_OBSERVERS and _RUN_OBSERVERS[key] != handler:
        raise ImproperlyConfigured(f"Observer esecuzione AI già registrato: {key}")
    _RUN_OBSERVERS[key] = handler


def notify_run_completed(run):
    for handler in tuple(_RUN_OBSERVERS.values()):
        handler(run=run)
