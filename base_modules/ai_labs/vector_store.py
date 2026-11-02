import os
import re
from urllib.parse import urlsplit

import requests
from rest_framework.exceptions import ValidationError

from .providers import validate_provider_url


def collection_name(knowledge_base):
    return f"mixtum_w{knowledge_base.workspace_id}_kb{knowledge_base.pk}_g{knowledge_base.index_generation}"


class QdrantStore:
    def __init__(self):
        raw_url = os.environ.get("QDRANT_URL", "http://127.0.0.1:6333")
        parsed = urlsplit(raw_url)
        if parsed.scheme == "http" and parsed.hostname == "qdrant" and not (
            parsed.username or parsed.password or parsed.query or parsed.fragment
        ):
            self.base_url = parsed.geturl().rstrip("/")
        else:
            self.base_url = validate_provider_url(raw_url)
        self.api_key = os.environ.get("QDRANT_API_KEY", "")
        self.session = requests.Session()
        self.session.trust_env = False

    def _request(self, method, path, **kwargs):
        response = self.session.request(
            method, f"{self.base_url}{path}", timeout=30, allow_redirects=False,
            headers={"api-key": self.api_key} if self.api_key else {}, **kwargs,
        )
        if response.is_redirect:
            raise ValidationError("Redirect Qdrant non consentito.")
        if response.status_code >= 400:
            raise ValidationError(f"Qdrant non disponibile ({response.status_code}).")
        return response.json() if response.content else {}

    def ensure_collection(self, name, vector_size):
        if not re.fullmatch(r"[a-zA-Z0-9_-]{1,255}", name):
            raise ValidationError("Nome collezione vettoriale non valido.")
        response = self.session.get(
            f"{self.base_url}/collections/{name}", timeout=10, allow_redirects=False,
            headers={"api-key": self.api_key} if self.api_key else {},
        )
        if response.status_code == 404:
            self._request("PUT", f"/collections/{name}", json={"vectors": {"size": vector_size, "distance": "Cosine"}})
        elif response.status_code >= 400:
            raise ValidationError(f"Qdrant non disponibile ({response.status_code}).")

    def upsert(self, name, points):
        self._request("PUT", f"/collections/{name}/points?wait=true", json={"points": points})

    def delete(self, name, point_ids):
        if point_ids:
            self._request("POST", f"/collections/{name}/points/delete?wait=true", json={"points": point_ids})

    def search(self, name, vector, limit):
        data = self._request(
            "POST", f"/collections/{name}/points/search",
            json={"vector": vector, "limit": min(max(limit, 1), 50), "with_payload": False},
        )
        return data.get("result", [])
