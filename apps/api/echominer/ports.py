"""Port definitions. The application layer depends on these, never on a vendor SDK."""
from typing import Any, BinaryIO, Protocol, Sequence


class Mailer(Protocol):
    def send(self, *, to: Sequence[str], subject: str, text: str, html: str | None = None,
             template: str = "generic") -> str: ...


class CaptchaVerifier(Protocol):
    def verify(self, token: str, *, action: str, remote_ip: str | None = None) -> bool: ...


class RawExtraction(Protocol):
    rows: list[dict[str, Any]]
    page_count: int
    warnings: list[str]


class ExtractionEngine(Protocol):
    version: str
    dictionary_version: str

    def extract(self, document: BinaryIO, *, filename: str) -> RawExtraction: ...
