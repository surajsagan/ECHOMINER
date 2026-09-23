"""Runtime configuration. Every value is environment-driven; nothing secret is committed."""
from functools import lru_cache
from typing import Literal
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # --- core -----------------------------------------------------------
    env: Literal["dev", "test", "prod"] = "dev"
    app_name: str = "EchoMiner"
    public_base_url: str = "http://localhost:3000"
    secret_key: str = Field(default="dev-only-change-me", min_length=8)
    log_level: str = "INFO"

    # --- database -------------------------------------------------------
    database_url: str = "postgresql+psycopg://echominer:echominer@localhost:5432/echominer"

    # --- registration ---------------------------------------------------
    # Open registration (ruling, 8 Aug 2026). The allow-list stays in the
    # config as an unused switch: if the platform is ever scoped back to
    # institutional users, it is one env var, not a code change.
    allowed_email_domains: str = ""

    # --- OTP / session --------------------------------------------------
    otp_ttl_seconds: int = 600
    otp_max_attempts: int = 5
    otp_length: int = 6
    otp_pepper: str = "dev-only-pepper"
    session_idle_seconds: int = 8 * 3600
    session_absolute_seconds: int = 24 * 3600
    trusted_device_days: int = 180

    # --- upload limits (ruling: 20 files) --------------------------------
    max_files_per_job: int = 20
    max_job_bytes: int = 200 * 1024 * 1024
    max_pages_per_file: int = 2000

    # --- staging ----------------------------------------------------------
    # RAM-backed volume shared by api and worker in production (docker-compose).
    spool_dir: str = "/var/echominer/spool"

    # --- single-service hosting (Render) --------------------------------
    # Run the extraction worker inside the API process instead of a separate
    # container, and serve the statically exported website from the API.
    embedded_worker: bool = False
    worker_poll_seconds: float = 2.0
    purge_interval_seconds: int = 300
    static_dir: str = ""
    # In-process per-IP rate limits (nginx does this on the VM deployment).
    app_rate_limit: bool = False
    # First administrator, created at start-up only if no administrator exists.
    admin_bootstrap_email: str = ""
    admin_bootstrap_password: str = ""

    # --- retention ------------------------------------------------------
    artefact_ttl_seconds: int = 2 * 3600

    # --- mail -----------------------------------------------------------
    # smtp: Brevo SMTP relay (VM hosting). brevo_api: Brevo HTTPS API, for hosts
    # that block outbound SMTP ports (Render free tier).
    mail_provider: Literal["console", "smtp", "brevo_api"] = "console"
    brevo_api_key: str = ""
    smtp_host: str = "smtp-relay.brevo.com"
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    mail_from: str = "noreply@echominer.in"
    mail_from_name: str = "EchoMiner"
    mail_reply_to: str = "aiechominer@gmail.com"
    mail_daily_quota: int = 300
    registration_notify: str = "surajbm@jssuni.edu.in,madhub@jssuni.edu.in,aiechominer@gmail.com"

    # --- captcha --------------------------------------------------------
    captcha_provider: Literal["null", "recaptcha"] = "null"
    recaptcha_secret: str = ""
    recaptcha_min_score: float = 0.5

    @field_validator("database_url")
    @classmethod
    def _psycopg_driver(cls, v: str) -> str:
        """Hosted Postgres providers (Neon, Render) hand out postgres:// or
        postgresql:// URLs; SQLAlchemy needs the psycopg 3 driver named."""
        v = v.strip()
        for prefix in ("postgres://", "postgresql://"):
            if v.startswith(prefix):
                return "postgresql+psycopg://" + v[len(prefix):]
        return v

    @field_validator("registration_notify", "allowed_email_domains")
    @classmethod
    def _strip(cls, v: str) -> str:
        return v.strip()

    @property
    def notify_addresses(self) -> list[str]:
        return [a.strip() for a in self.registration_notify.split(",") if a.strip()]

    @property
    def domain_allow_list(self) -> list[str]:
        return [d.strip().lower().lstrip("@") for d in self.allowed_email_domains.split(",") if d.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
