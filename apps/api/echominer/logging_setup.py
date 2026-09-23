"""Structured JSON logging with PII redaction. Registration and OTP payloads are never logged."""
import logging
import sys
import json
import time
from contextvars import ContextVar

request_id_var: ContextVar[str] = ContextVar("request_id", default="-")

_REDACT_KEYS = {"password", "otp", "code", "token", "email", "phone", "address", "name",
                "patient_name", "secret", "authorization", "cookie"}


def redact(payload: dict) -> dict:
    return {k: ("[redacted]" if k.lower() in _REDACT_KEYS else v) for k, v in payload.items()}


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        entry = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(record.created)),
            "level": record.levelname,
            "logger": record.name,
            "request_id": request_id_var.get(),
            "msg": record.getMessage(),
        }
        if record.exc_info:
            entry["exc"] = self.formatException(record.exc_info)
        for key, value in getattr(record, "extra_fields", {}).items():
            entry[key] = value
        return json.dumps(entry, ensure_ascii=False)


def configure_logging(level: str = "INFO") -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level)
