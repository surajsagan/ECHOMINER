"""Administration and analytics (M9) plus content management (M10)."""
from __future__ import annotations

import csv
import io
import uuid
from datetime import timedelta
from typing import Any, Optional

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from ..config import Settings
from ..models import (Admin, AdminSession, AuditEvent, ContentItem, Download, EmailLog,
                      ExtractionJob, JobFile, OtpChallenge, User)
from ..security import (expires_in, hash_password, hash_token, new_token, now,
                        verify_password, verify_totp)

ADMIN_SESSION_COOKIE = "__Host-em_admin"
ADMIN_IDLE_SECONDS = 15 * 60

CONTENT_KINDS = {"news", "publication", "faq"}


class AdminAuthError(Exception):
    pass


class AdminService:
    def __init__(self, db: Session, settings: Settings):
        self.db = db
        self.settings = settings

    # ---------------------------------------------------------------- auth --
    def create_admin(self, *, email: str, password: str, totp_secret: str | None = None,
                     role: str = "admin") -> Admin:
        admin = Admin(email=email.strip().lower(), password_hash=hash_password(password),
                      totp_secret_enc=totp_secret.encode() if totp_secret else None, role=role)
        self.db.add(admin)
        self.db.flush()
        return admin

    def login(self, *, email: str, password: str, totp_code: str | None,
              ip: str | None = None) -> str:
        admin = self.db.scalar(select(Admin).where(Admin.email == email.strip().lower()))
        # Verify a dummy hash when the account is unknown so a missing account and
        # a wrong password take the same time.
        encoded = admin.password_hash if admin else hash_password("not-a-real-password")
        password_ok = verify_password(password, encoded)

        if not admin or not admin.is_active or not password_ok:
            self._audit("admin.login_failed", target_id=email, ip=ip)
            self.db.commit()
            raise AdminAuthError("invalid credentials")

        if admin.totp_secret_enc:
            secret = admin.totp_secret_enc.decode()
            if not totp_code or not verify_totp(secret, totp_code):
                self._audit("admin.totp_failed", actor_id=admin.id, ip=ip)
                self.db.commit()
                raise AdminAuthError("invalid credentials")

        token = new_token()
        self.db.add(AdminSession(admin_id=admin.id, token_hash=hash_token(token),
                                 absolute_expiry=expires_in(ADMIN_IDLE_SECONDS * 4), ip=ip))
        self._audit("admin.login", actor_id=admin.id, ip=ip)
        self.db.flush()
        return token

    def resolve(self, token: str) -> Optional[Admin]:
        row = self.db.scalar(select(AdminSession).where(AdminSession.token_hash == hash_token(token)))
        if row is None or row.revoked_at or row.absolute_expiry <= now():
            return None
        if (now() - row.last_seen_at).total_seconds() > ADMIN_IDLE_SECONDS:
            row.revoked_at = now()
            return None
        admin = self.db.get(Admin, row.admin_id)
        if admin is None or not admin.is_active:
            return None
        row.last_seen_at = now()
        return admin

    def sign_out(self, token: str) -> None:
        row = self.db.scalar(select(AdminSession).where(AdminSession.token_hash == hash_token(token)))
        if row and not row.revoked_at:
            row.revoked_at = now()

    def _audit(self, action: str, *, actor_id=None, target_type: str | None = None,
               target_id: str | None = None, ip: str | None = None, metadata: dict | None = None):
        self.db.add(AuditEvent(actor_type="admin", actor_id=actor_id, action=action,
                               target_type=target_type, target_id=target_id, ip=ip,
                               metadata_json=metadata))

    # --------------------------------------------------------------- users --
    def users(self, *, search: str | None = None, state: str | None = None,
              country: str | None = None, status: str | None = None,
              limit: int = 50, offset: int = 0) -> dict[str, Any]:
        stmt = select(User)
        if search:
            term = f"%{search.strip().lower()}%"
            stmt = stmt.where(or_(func.lower(User.full_name).like(term),
                                  func.lower(User.email).like(term),
                                  func.lower(User.institute).like(term),
                                  func.lower(User.affiliation).like(term)))
        if state:
            stmt = stmt.where(User.state == state)
        if country:
            stmt = stmt.where(User.country_iso2 == country.upper())
        if status:
            stmt = stmt.where(User.status == status)

        total = self.db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
        rows = self.db.scalars(
            stmt.order_by(User.created_at.desc()).limit(min(limit, 200)).offset(offset)).all()
        return {"total": total, "items": [self._user_row(u) for u in rows]}

    @staticmethod
    def _user_row(user: User) -> dict[str, Any]:
        return {
            "id": str(user.id), "email": user.email, "full_name": user.full_name,
            "designation": user.designation, "affiliation": user.affiliation,
            "institute": user.institute, "taluk": user.taluk, "district": user.district,
            "state": user.state, "country_iso2": user.country_iso2,
            "phone_e164": user.phone_e164, "project_title": user.project_title,
            "project_description": user.project_description, "purpose": user.purpose,
            "status": user.status,
            "email_verified_at": user.email_verified_at.isoformat() if user.email_verified_at else None,
            "created_at": user.created_at.isoformat() if user.created_at else None,
        }

    def users_csv(self) -> str:
        rows = self.db.scalars(select(User).order_by(User.created_at)).all()
        buffer = io.StringIO()
        if not rows:
            return ""
        fields = list(self._user_row(rows[0]).keys())
        writer = csv.DictWriter(buffer, fieldnames=fields)
        writer.writeheader()
        for user in rows:
            writer.writerow(self._user_row(user))
        return buffer.getvalue()

    def set_user_status(self, user_id: str, status: str) -> None:
        if status not in {"pending", "active", "disabled"}:
            raise ValueError("invalid status")
        user = self.db.get(User, uuid.UUID(str(user_id)))
        if user is None:
            raise KeyError(user_id)
        user.status = status
        self._audit("admin.user_status", target_type="user", target_id=str(user.id),
                    metadata={"status": status})

    # ------------------------------------------------------------ otp logs --
    def otp_log(self, limit: int = 100) -> list[dict[str, Any]]:
        """Delivery and verification outcomes. The code itself is stored only as a
        hash and is never exposed here."""
        rows = self.db.scalars(
            select(OtpChallenge).order_by(OtpChallenge.created_at.desc()).limit(limit)).all()
        return [{
            "email": r.email, "purpose": r.purpose, "attempts": r.attempts,
            "verified": r.consumed_at is not None,
            "locked": bool(r.locked_until and r.locked_until > now()),
            "expires_at": r.expires_at.isoformat(),
            "created_at": r.created_at.isoformat() if r.created_at else None,
        } for r in rows]

    def email_log(self, limit: int = 100) -> list[dict[str, Any]]:
        rows = self.db.scalars(
            select(EmailLog).order_by(EmailLog.created_at.desc()).limit(limit)).all()
        return [{"recipient": r.recipient, "template": r.template, "status": r.status,
                 "error": r.error,
                 "created_at": r.created_at.isoformat() if r.created_at else None} for r in rows]

    # ----------------------------------------------------------- analytics --
    def usage_summary(self) -> dict[str, Any]:
        jobs = self.db.scalar(select(func.count()).select_from(ExtractionJob)) or 0
        return {
            "users_total": self.db.scalar(select(func.count()).select_from(User)) or 0,
            "users_active": self.db.scalar(
                select(func.count()).select_from(User).where(User.status == "active")) or 0,
            "jobs_total": jobs,
            "files_total": self.db.scalar(select(func.count()).select_from(JobFile)) or 0,
            "records_total": self.db.scalar(select(func.coalesce(func.sum(ExtractionJob.record_count), 0))) or 0,
            "downloads_total": self.db.scalar(select(func.count()).select_from(Download)) or 0,
        }

    def timeseries(self, days: int = 30) -> list[dict[str, Any]]:
        since = now() - timedelta(days=days)
        def by_day(model, column):
            rows = self.db.execute(
                select(func.date(column).label("day"), func.count())
                .where(column >= since).group_by("day")).all()
            return {str(day): count for day, count in rows}

        users = by_day(User, User.created_at)
        jobs = by_day(ExtractionJob, ExtractionJob.created_at)
        downloads = by_day(Download, Download.created_at)
        days_set = sorted(set(users) | set(jobs) | set(downloads))
        return [{"day": day, "registrations": users.get(day, 0),
                 "jobs": jobs.get(day, 0), "downloads": downloads.get(day, 0)}
                for day in days_set]

    def _grouped(self, column, label: str, *, limit: int = 25) -> list[dict[str, Any]]:
        rows = self.db.execute(
            select(column, func.count()).group_by(column)
            .order_by(func.count().desc()).limit(limit)).all()
        return [{label: value or "Unspecified", "count": count} for value, count in rows]

    def geography(self) -> dict[str, Any]:
        return {"states": self._grouped(User.state, "state"),
                "countries": self._grouped(User.country_iso2, "country")}

    def projects(self) -> list[dict[str, Any]]:
        return self._grouped(User.project_title, "project", limit=50)

    # -------------------------------------------------------------- health --
    def health(self) -> dict[str, Any]:
        queued = self.db.scalar(select(func.count()).select_from(ExtractionJob)
                                .where(ExtractionJob.status == "queued")) or 0
        running = self.db.scalar(select(func.count()).select_from(ExtractionJob)
                                 .where(ExtractionJob.status == "running")) or 0
        overdue = self.db.scalar(
            select(func.count()).select_from(ExtractionJob)
            .where(ExtractionJob.purged_at.is_(None),
                   ExtractionJob.purge_after.is_not(None),
                   ExtractionJob.purge_after <= now())) or 0
        failed = self.db.scalar(select(func.count()).select_from(ExtractionJob)
                                .where(ExtractionJob.status == "failed")) or 0
        return {"queue_depth": queued, "running": running,
                "purge_backlog": overdue, "failed_jobs": failed,
                # A purge backlog is a P1: it means report files are outliving
                # their retention window.
                "status": "degraded" if overdue else "ok"}

    # ------------------------------------------------------------- content --
    def content(self, kind: str, *, published_only: bool = False) -> list[dict[str, Any]]:
        if kind not in CONTENT_KINDS:
            raise ValueError("unknown content kind")
        stmt = select(ContentItem).where(ContentItem.kind == kind)
        if published_only:
            stmt = stmt.where(ContentItem.published_at.is_not(None))
        rows = self.db.scalars(
            stmt.order_by(ContentItem.sort_order, ContentItem.published_at.desc())).all()
        return [self._content_row(item) for item in rows]

    @staticmethod
    def _content_row(item: ContentItem) -> dict[str, Any]:
        return {"id": str(item.id), "kind": item.kind, "slug": item.slug, "title": item.title,
                "body_md": item.body_md, "link_url": item.link_url,
                "published_at": item.published_at.isoformat() if item.published_at else None,
                "sort_order": item.sort_order}

    def upsert_content(self, *, kind: str, slug: str, title: str, body_md: str,
                       link_url: str | None = None, published: bool = False,
                       sort_order: int = 0, item_id: str | None = None) -> dict[str, Any]:
        if kind not in CONTENT_KINDS:
            raise ValueError("unknown content kind")
        item = self.db.get(ContentItem, uuid.UUID(item_id)) if item_id else None
        if item is None:
            item = self.db.scalar(select(ContentItem).where(ContentItem.kind == kind,
                                                            ContentItem.slug == slug))
        if item is None:
            item = ContentItem(kind=kind, slug=slug)
            self.db.add(item)
        item.title, item.body_md, item.link_url, item.sort_order = title, body_md, link_url, sort_order
        item.published_at = now() if published else None
        self.db.flush()
        self._audit("admin.content_saved", target_type="content", target_id=str(item.id))
        return self._content_row(item)

    def delete_content(self, item_id: str) -> None:
        item = self.db.get(ContentItem, uuid.UUID(item_id))
        if item is None:
            raise KeyError(item_id)
        self.db.delete(item)
        self._audit("admin.content_deleted", target_type="content", target_id=item_id)

    # --------------------------------------------------------------- audit --
    def audit(self, limit: int = 100) -> list[dict[str, Any]]:
        rows = self.db.scalars(
            select(AuditEvent).order_by(AuditEvent.created_at.desc()).limit(limit)).all()
        return [{"action": r.action, "actor_type": r.actor_type,
                 "actor_id": str(r.actor_id) if r.actor_id else None,
                 "target_type": r.target_type, "target_id": r.target_id, "ip": r.ip,
                 "metadata": r.metadata_json,
                 "created_at": r.created_at.isoformat() if r.created_at else None} for r in rows]
