"""Captcha adapters behind a port, so reCAPTCHA can be swapped for Turnstile
without touching a single call site."""
import logging
import httpx
from ..config import Settings

log = logging.getLogger(__name__)
VERIFY_URL = "https://www.google.com/recaptcha/api/siteverify"


class NullCaptcha:
    """Dev/test adapter: accepts any non-empty token."""

    def verify(self, token: str, *, action: str, remote_ip: str | None = None) -> bool:
        return bool(token)


class RecaptchaV3:
    def __init__(self, settings: Settings):
        self.settings = settings

    def verify(self, token: str, *, action: str, remote_ip: str | None = None) -> bool:
        if not token:
            return False
        payload = {"secret": self.settings.recaptcha_secret, "response": token}
        if remote_ip:
            payload["remoteip"] = remote_ip
        try:
            data = httpx.post(VERIFY_URL, data=payload, timeout=10).json()
        except Exception:
            log.warning("captcha verify failed; failing closed")
            return False
        if not data.get("success"):
            return False
        if data.get("action") and data["action"] != action:
            return False
        return float(data.get("score", 0)) >= self.settings.recaptcha_min_score


def build_captcha(settings: Settings):
    return RecaptchaV3(settings) if settings.captcha_provider == "recaptcha" else NullCaptcha()
