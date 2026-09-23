"""SQLAlchemy 2.0 models. Schema mirrors §6 of the architecture document."""
from __future__ import annotations
import uuid
from datetime import datetime, timezone as _tz
from typing import Any, Optional
from sqlalchemy import (BigInteger, Boolean, DateTime, ForeignKey, Index, Integer,
                        LargeBinary, Numeric, SmallInteger, String, Text, UniqueConstraint, func)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.types import JSON, TypeDecorator, CHAR

_utc = _tz.utc


class GUID(TypeDecorator):
    """UUID that works on both PostgreSQL and SQLite (test runs)."""
    impl = CHAR
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            from sqlalchemy.dialects.postgresql import UUID as PGUUID
            return dialect.type_descriptor(PGUUID(as_uuid=True))
        return dialect.type_descriptor(CHAR(36))

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        return value if dialect.name == "postgresql" else str(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        return value if isinstance(value, uuid.UUID) else uuid.UUID(str(value))


JSONType = JSON().with_variant(JSONB, "postgresql")


class TZDateTime(TypeDecorator):
    """Timezone-aware timestamps on every backend.

    Postgres stores timestamptz natively; SQLite drops tzinfo, which makes a
    naive value leak into comparisons against aware ones. Normalising on the way
    in and out keeps expiry checks correct regardless of backend.
    """
    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is not None and value.tzinfo is None:
            value = value.replace(tzinfo=_utc)
        return value

    def process_result_value(self, value, dialect):
        if value is not None and value.tzinfo is None:
            value = value.replace(tzinfo=_utc)
        return value


class Base(DeclarativeBase):
    pass


def _pk() -> Mapped[uuid.UUID]:
    return mapped_column(GUID(), primary_key=True, default=uuid.uuid4)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(TZDateTime(), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(TZDateTime(), server_default=func.now(), onupdate=func.now())


class User(Base, TimestampMixin):
    __tablename__ = "users"
    id: Mapped[uuid.UUID] = _pk()
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(200))
    designation: Mapped[str] = mapped_column(String(200))
    affiliation: Mapped[str] = mapped_column(String(300))
    institute: Mapped[str] = mapped_column(String(300))
    taluk: Mapped[Optional[str]] = mapped_column(String(120))
    district: Mapped[Optional[str]] = mapped_column(String(120))
    state: Mapped[Optional[str]] = mapped_column(String(120))
    country_iso2: Mapped[str] = mapped_column(String(2), index=True)
    phone_e164: Mapped[Optional[str]] = mapped_column(String(20))
    project_title: Mapped[str] = mapped_column(String(300))
    project_description: Mapped[str] = mapped_column(Text)
    purpose: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)  # pending|active|disabled
    email_verified_at: Mapped[Optional[datetime]] = mapped_column(TZDateTime())
    last_login_at: Mapped[Optional[datetime]] = mapped_column(TZDateTime())

    acceptances: Mapped[list["AgreementAcceptance"]] = relationship(back_populates="user")


class AgreementAcceptance(Base):
    """Stores the SHA-256 of the exact text accepted, so what a user agreed to is provable."""
    __tablename__ = "agreement_acceptances"
    id: Mapped[uuid.UUID] = _pk()
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    agreement_version: Mapped[str] = mapped_column(String(20))
    text_sha256: Mapped[bytes] = mapped_column(LargeBinary(32))
    accepted_at: Mapped[datetime] = mapped_column(TZDateTime(), server_default=func.now())
    ip: Mapped[Optional[str]] = mapped_column(String(45))
    user_agent: Mapped[Optional[str]] = mapped_column(String(400))
    user: Mapped["User"] = relationship(back_populates="acceptances")


class OtpChallenge(Base):
    __tablename__ = "otp_challenges"
    id: Mapped[uuid.UUID] = _pk()
    email: Mapped[str] = mapped_column(String(320), index=True)
    code_hash: Mapped[bytes] = mapped_column(LargeBinary(32))
    purpose: Mapped[str] = mapped_column(String(30), default="registration")
    attempts: Mapped[int] = mapped_column(SmallInteger, default=0)
    expires_at: Mapped[datetime] = mapped_column(TZDateTime(), index=True)
    consumed_at: Mapped[Optional[datetime]] = mapped_column(TZDateTime())
    locked_until: Mapped[Optional[datetime]] = mapped_column(TZDateTime())
    request_ip: Mapped[Optional[str]] = mapped_column(String(45))
    created_at: Mapped[datetime] = mapped_column(TZDateTime(), server_default=func.now())


class Session(Base):
    __tablename__ = "sessions"
    id: Mapped[uuid.UUID] = _pk()
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    token_hash: Mapped[bytes] = mapped_column(LargeBinary(32), unique=True)
    issued_at: Mapped[datetime] = mapped_column(TZDateTime(), server_default=func.now())
    last_seen_at: Mapped[datetime] = mapped_column(TZDateTime(), server_default=func.now())
    absolute_expiry: Mapped[datetime] = mapped_column(TZDateTime())
    revoked_at: Mapped[Optional[datetime]] = mapped_column(TZDateTime())
    ip: Mapped[Optional[str]] = mapped_column(String(45))
    user_agent: Mapped[Optional[str]] = mapped_column(String(400))


class TrustedDevice(Base):
    """Selector/validator pair, rotated on every use. Validator reuse signals theft."""
    __tablename__ = "trusted_devices"
    id: Mapped[uuid.UUID] = _pk()
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    selector: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    validator_hash: Mapped[bytes] = mapped_column(LargeBinary(32))
    expires_at: Mapped[datetime] = mapped_column(TZDateTime())
    last_seen_at: Mapped[datetime] = mapped_column(TZDateTime(), server_default=func.now())
    revoked_at: Mapped[Optional[datetime]] = mapped_column(TZDateTime())
    created_at: Mapped[datetime] = mapped_column(TZDateTime(), server_default=func.now())


class EmailLog(Base):
    __tablename__ = "email_log"
    id: Mapped[uuid.UUID] = _pk()
    recipient: Mapped[str] = mapped_column(String(320), index=True)
    template: Mapped[str] = mapped_column(String(60))
    status: Mapped[str] = mapped_column(String(20))  # sent|failed|quota_blocked
    provider_message_id: Mapped[Optional[str]] = mapped_column(String(200))
    error: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(TZDateTime(), server_default=func.now(), index=True)


class ExtractionJob(Base):
    __tablename__ = "extraction_jobs"
    id: Mapped[uuid.UUID] = _pk()
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    status: Mapped[str] = mapped_column(String(20), default="received", index=True)
    file_count: Mapped[int] = mapped_column(SmallInteger, default=0)
    total_bytes: Mapped[int] = mapped_column(BigInteger, default=0)
    record_count: Mapped[int] = mapped_column(Integer, default=0)
    engine_version: Mapped[Optional[str]] = mapped_column(String(60))
    dictionary_version: Mapped[Optional[str]] = mapped_column(String(20))
    error_code: Mapped[Optional[str]] = mapped_column(String(60))
    started_at: Mapped[Optional[datetime]] = mapped_column(TZDateTime())
    finished_at: Mapped[Optional[datetime]] = mapped_column(TZDateTime())
    purge_after: Mapped[Optional[datetime]] = mapped_column(TZDateTime(), index=True)
    purged_at: Mapped[Optional[datetime]] = mapped_column(TZDateTime())
    created_at: Mapped[datetime] = mapped_column(TZDateTime(), server_default=func.now(), index=True)


class JobFile(Base):
    __tablename__ = "job_files"
    id: Mapped[uuid.UUID] = _pk()
    job_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("extraction_jobs.id", ondelete="CASCADE"), index=True)
    original_filename: Mapped[str] = mapped_column(String(400))
    sha256: Mapped[bytes] = mapped_column(LargeBinary(32))
    size_bytes: Mapped[int] = mapped_column(BigInteger)
    page_count: Mapped[Optional[int]] = mapped_column(Integer)
    record_count: Mapped[int] = mapped_column(Integer, default=0)
    blank_row_count: Mapped[int] = mapped_column(Integer, default=0)
    header_count: Mapped[Optional[int]] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20), default="pending")
    error_code: Mapped[Optional[str]] = mapped_column(String(60))
    warnings: Mapped[Optional[str]] = mapped_column(Text)


class ExtractionRecord(Base):
    __tablename__ = "extraction_records"
    id: Mapped[uuid.UUID] = _pk()
    job_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("extraction_jobs.id", ondelete="CASCADE"), index=True)
    file_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("job_files.id", ondelete="CASCADE"), index=True)
    seq: Mapped[int] = mapped_column(Integer)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONType)
    dictionary_version: Mapped[str] = mapped_column(String(20))
    completeness: Mapped[Optional[float]] = mapped_column(Numeric(5, 1))


class Download(Base):
    __tablename__ = "downloads"
    id: Mapped[uuid.UUID] = _pk()
    job_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("extraction_jobs.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    format: Mapped[str] = mapped_column(String(20))
    bytes: Mapped[int] = mapped_column(BigInteger)
    created_at: Mapped[datetime] = mapped_column(TZDateTime(), server_default=func.now(), index=True)


class AuditEvent(Base):
    """Append-only. A DB trigger blocks UPDATE/DELETE in the Postgres migration."""
    __tablename__ = "audit_events"
    # BigInteger does not autoincrement on SQLite (test runs); the variant keeps
    # bigserial semantics on Postgres and plain INTEGER rowid on SQLite.
    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    actor_type: Mapped[str] = mapped_column(String(20))
    actor_id: Mapped[Optional[uuid.UUID]] = mapped_column(GUID())
    action: Mapped[str] = mapped_column(String(60), index=True)
    target_type: Mapped[Optional[str]] = mapped_column(String(40))
    target_id: Mapped[Optional[str]] = mapped_column(String(64))
    ip: Mapped[Optional[str]] = mapped_column(String(45))
    request_id: Mapped[Optional[str]] = mapped_column(String(64))
    metadata_json: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONType)
    created_at: Mapped[datetime] = mapped_column(TZDateTime(), server_default=func.now(), index=True)


class Admin(Base, TimestampMixin):
    __tablename__ = "admins"
    id: Mapped[uuid.UUID] = _pk()
    email: Mapped[str] = mapped_column(String(320), unique=True)
    password_hash: Mapped[str] = mapped_column(String(200))
    totp_secret_enc: Mapped[Optional[bytes]] = mapped_column(LargeBinary(200))
    role: Mapped[str] = mapped_column(String(20), default="admin")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class AdminSession(Base):
    """Administrator sessions live in their own table, not in `sessions`.

    Sharing the user session table would mean an admin id sitting in a column
    with a foreign key to `users` -- the two realms must not be able to reference
    each other at all.
    """
    __tablename__ = "admin_sessions"
    id: Mapped[uuid.UUID] = _pk()
    admin_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("admins.id", ondelete="CASCADE"), index=True)
    token_hash: Mapped[bytes] = mapped_column(LargeBinary(32), unique=True)
    issued_at: Mapped[datetime] = mapped_column(TZDateTime(), server_default=func.now())
    last_seen_at: Mapped[datetime] = mapped_column(TZDateTime(), server_default=func.now())
    absolute_expiry: Mapped[datetime] = mapped_column(TZDateTime())
    revoked_at: Mapped[Optional[datetime]] = mapped_column(TZDateTime())
    ip: Mapped[Optional[str]] = mapped_column(String(45))


class ContentItem(Base, TimestampMixin):
    """Shared table for news, publications and FAQ entries."""
    __tablename__ = "content_items"
    __table_args__ = (UniqueConstraint("kind", "slug", name="uq_content_kind_slug"),
                      Index("ix_content_kind_published", "kind", "published_at"))
    id: Mapped[uuid.UUID] = _pk()
    kind: Mapped[str] = mapped_column(String(20))  # news|publication|faq
    slug: Mapped[str] = mapped_column(String(200))
    title: Mapped[str] = mapped_column(String(400))
    body_md: Mapped[str] = mapped_column(Text)
    link_url: Mapped[Optional[str]] = mapped_column(String(500))
    published_at: Mapped[Optional[datetime]] = mapped_column(TZDateTime())
    sort_order: Mapped[int] = mapped_column(Integer, default=0)


class FieldDictionary(Base):
    __tablename__ = "field_dictionaries"
    version: Mapped[str] = mapped_column(String(20), primary_key=True)
    spec: Mapped[dict[str, Any]] = mapped_column(JSONType)
    effective_from: Mapped[datetime] = mapped_column(TZDateTime(), server_default=func.now())
