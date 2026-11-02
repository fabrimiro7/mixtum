import ipaddress
import os
import socket
import time
from dataclasses import dataclass
from decimal import Decimal, ROUND_CEILING
from urllib.parse import urlsplit

import requests
from rest_framework.exceptions import ValidationError


@dataclass(frozen=True)
class ProviderResult:
    output: dict
    prompt_tokens: int | None
    completion_tokens: int | None
    total_tokens: int | None
    latency_ms: int
    provider_request_id: str = ""


def validate_provider_url(base_url, *, resolve=True):
    parsed = urlsplit(base_url.rstrip("/"))
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValidationError("Endpoint provider HTTP/HTTPS non valido.")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValidationError("Endpoint provider non può contenere credenziali, query o fragment.")
    if parsed.scheme == "http" and parsed.hostname not in {"127.0.0.1", "localhost"}:
        raise ValidationError("Endpoint provider HTTP ammesso soltanto su loopback.")
    if parsed.hostname != "localhost" and resolve:
        try:
            address = ipaddress.ip_address(parsed.hostname)
        except ValueError:
            try:
                addresses = {ipaddress.ip_address(item[4][0]) for item in socket.getaddrinfo(parsed.hostname, parsed.port or 443)}
            except OSError as exc:
                raise ValidationError("Endpoint provider non risolvibile.") from exc
            if any(address.is_private or address.is_link_local or address.is_loopback for address in addresses):
                raise ValidationError("Endpoint provider risolve verso una rete non consentita.")
        else:
            if parsed.scheme == "https" and (address.is_private or address.is_link_local or address.is_loopback):
                raise ValidationError("Endpoint provider verso rete privata non consentito.")
    return parsed.geturl().rstrip("/")


def estimate_tokens(messages, max_output_tokens):
    text = " ".join(str(item.get("content", "")) for item in messages if isinstance(item, dict))
    return max(1, (len(text) + 3) // 4) + max_output_tokens


def estimate_cost_microunits(model, prompt_tokens, completion_tokens):
    if model.prompt_cost_per_million is None or model.completion_cost_per_million is None:
        return None
    value = Decimal(prompt_tokens) * model.prompt_cost_per_million + Decimal(completion_tokens) * model.completion_cost_per_million
    return int(value.to_integral_value(rounding=ROUND_CEILING))


class OpenAiCompatibleClient:
    def complete(self, *, model, messages, max_output_tokens=1024, tools=None):
        provider = model.provider
        base_url = validate_provider_url(provider.base_url)
        api_key = os.environ.get(provider.api_key_env_var, "") if provider.api_key_env_var else ""
        if provider.api_key_env_var and not api_key:
            raise ValidationError(f"Secret provider non configurato: {provider.api_key_env_var}.")
        body = {"model": model.model_id, "messages": messages, "max_tokens": max_output_tokens}
        if tools:
            body["tools"] = tools
        session = requests.Session()
        session.trust_env = False
        started = time.perf_counter()
        response = session.post(
            f"{base_url}/chat/completions",
            json=body,
            headers={"Authorization": f"Bearer {api_key}"} if api_key else {},
            timeout=min(provider.timeout_seconds, 300),
            allow_redirects=False,
        )
        latency = int((time.perf_counter() - started) * 1000)
        if response.is_redirect:
            raise ValidationError("Redirect provider non consentito.")
        response.raise_for_status()
        data = response.json()
        usage = data.get("usage") if isinstance(data, dict) else None
        choice = (data.get("choices") or [{}])[0]
        message = choice.get("message") or {}
        return ProviderResult(
            output={"message": message, "finish_reason": choice.get("finish_reason")},
            prompt_tokens=usage.get("prompt_tokens") if isinstance(usage, dict) else None,
            completion_tokens=usage.get("completion_tokens") if isinstance(usage, dict) else None,
            total_tokens=usage.get("total_tokens") if isinstance(usage, dict) else None,
            latency_ms=latency,
            provider_request_id=response.headers.get("x-request-id", ""),
        )

    def embed(self, *, model, inputs):
        provider = model.provider
        base_url = validate_provider_url(provider.base_url)
        api_key = os.environ.get(provider.api_key_env_var, "") if provider.api_key_env_var else ""
        if provider.api_key_env_var and not api_key:
            raise ValidationError(f"Secret provider non configurato: {provider.api_key_env_var}.")
        session = requests.Session()
        session.trust_env = False
        started = time.perf_counter()
        response = session.post(
            f"{base_url}/embeddings",
            json={"model": model.model_id, "input": inputs},
            headers={"Authorization": f"Bearer {api_key}"} if api_key else {},
            timeout=min(provider.timeout_seconds, 300),
            allow_redirects=False,
        )
        latency = int((time.perf_counter() - started) * 1000)
        if response.is_redirect:
            raise ValidationError("Redirect provider non consentito.")
        response.raise_for_status()
        data = response.json()
        vectors = [item.get("embedding") for item in sorted(data.get("data", []), key=lambda item: item.get("index", 0))]
        if len(vectors) != len(inputs) or not all(isinstance(vector, list) for vector in vectors):
            raise ValidationError("Risposta embedding non valida.")
        usage = data.get("usage") or {}
        return vectors, usage.get("total_tokens") or usage.get("prompt_tokens"), latency


def client_for_model(model):
    if model.provider.kind not in {model.provider.REGOLO, model.provider.OPENAI_COMPATIBLE}:
        raise ValidationError("Tipo provider non supportato.")
    return OpenAiCompatibleClient()
