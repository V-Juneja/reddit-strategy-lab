import re

PATTERNS = {
    "personal-path": re.compile(r"/(?:Users|home)/[A-Za-z0-9_.-]+"),
    "private-key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    "api-secret": re.compile(r"(?:sk-[A-Za-z0-9_-]{16,}|gh[pousr]_[A-Za-z0-9]{20,}|AKIA[A-Z0-9]{16})"),
    "secret-assignment": re.compile(
        r'(?i)(?:api_key|access_token|password|client_secret)\s*[=:]\s*["\']?(?!YOUR_|false|None|os\.|\$|\{|\[)[A-Za-z0-9_/-]{20,}'
    ),
    "account-data": re.compile(r"(?i)(?:account_number|routing_number|social_security_number)\s*[=:]"),
}


def findings(text):
    return [category for category, pattern in PATTERNS.items() if pattern.search(text)]


def safe_model_input(text):
    if findings(text):
        raise ValueError(
            "source may contain credentials/private paths; redact locally before model extraction"
        )
    return text


def error_reason(exc):
    """Only fixed, locally authored ValueErrors are safe to expose without source payloads."""
    from pydantic import ValidationError

    if hasattr(exc, "audit") and hasattr(exc, "status"):
        return (
            "source-native "
            + exc.status
            + "; inspect data/source-audits for exact requirements and missing parameters"
        )
    if isinstance(exc, ValidationError):
        return "schema validation failed (invalid fields, unsupported grammar or incomplete evidence)"
    if type(exc) is ValueError and len(str(exc)) <= 180 and not findings(str(exc)):
        return str(exc)
    return type(exc).__name__ + ": check access, data and configuration; source payload withheld"
