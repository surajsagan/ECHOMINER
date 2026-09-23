"""Mail adapters. Console for dev/test, SMTP relay (Brevo) for production.

Sending as noreply@echominer.in requires DNS records only -- SPF, DKIM CNAMEs and
DMARC on the domain. No mailbox is created; replies are routed by Reply-To.
"""
import logging
import smtplib
import uuid
from email.message import EmailMessage
from email.utils import formataddr
from typing import Sequence
from ..config import Settings

log = logging.getLogger(__name__)


class ConsoleMailer:
    """Dev/test adapter. Captures messages instead of sending them."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.outbox: list[dict] = []

    def send(self, *, to: Sequence[str], subject: str, text: str, html: str | None = None,
             template: str = "generic") -> str:
        message_id = f"console-{uuid.uuid4()}"
        self.outbox.append({"to": list(to), "subject": subject, "text": text,
                            "html": html, "template": template, "id": message_id})
        log.info("mail captured", extra={"extra_fields": {"template": template, "recipients": len(to)}})
        if self.settings.env == "dev":
            # Local development only: show the message (including OTP codes) in the terminal.
            import sys
            print(f"\n----- DEV MAIL to {', '.join(to)} -----\nSubject: {subject}\n\n{text}\n"
                  "-----------------------------------------\n", file=sys.stderr, flush=True)
        return message_id


class SmtpMailer:
    def __init__(self, settings: Settings):
        self.settings = settings

    def send(self, *, to: Sequence[str], subject: str, text: str, html: str | None = None,
             template: str = "generic") -> str:
        s = self.settings
        msg = EmailMessage()
        msg["From"] = formataddr((s.mail_from_name, s.mail_from))
        msg["To"] = ", ".join(to)
        msg["Reply-To"] = s.mail_reply_to
        msg["Subject"] = subject
        msg.set_content(text)
        if html:
            msg.add_alternative(html, subtype="html")
        with smtplib.SMTP(s.smtp_host, s.smtp_port, timeout=20) as smtp:
            smtp.starttls()
            if s.smtp_user:
                smtp.login(s.smtp_user, s.smtp_password)
            smtp.send_message(msg)
        return msg.get("Message-ID", "smtp-sent")


def build_mailer(settings: Settings):
    return SmtpMailer(settings) if settings.mail_provider == "smtp" else ConsoleMailer(settings)
