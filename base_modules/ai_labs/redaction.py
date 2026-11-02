import re


SENSITIVE_PARTS = ("authorization", "password", "secret", "token", "api_key", "apikey", "key")
_BEARER = re.compile(r"(?i)bearer\s+[a-z0-9._~+/-]+")


def redact(value, *, max_chars=8000):
    if isinstance(value, dict):
        return {
            key: "[REDACTED]" if any(part in str(key).lower() for part in SENSITIVE_PARTS) else redact(item, max_chars=max_chars)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [redact(item, max_chars=max_chars) for item in value]
    if isinstance(value, str):
        if value.startswith("data:image"):
            return "[IMAGE_REMOVED]"
        cleaned = _BEARER.sub("Bearer [REDACTED]", value)
        return cleaned if len(cleaned) <= max_chars else cleaned[:max_chars] + "…[truncated]"
    return value
