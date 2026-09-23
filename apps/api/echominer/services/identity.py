"""Identity use cases: registration, OTP verification, sessions, trusted devices.

Implements §8 of the architecture document. Open registration (ruling 8 Aug 2026):
any email may register. The domain allow-list is read from config and is empty by
default, so the check is a no-op unless the platform is later scoped back.
"""
from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import Settings
from ..models import (AgreementAcceptance, AuditEvent, OtpChallenge, Session as SessionRow,
                      TrustedDevice, User)
from ..security import (expires_in, generate_otp, hash_otp, hash_token, new_device_pair,
                        new_token, now, verify_otp)

log = logging.getLogger(__name__)

AGREEMENT_VERSION = "1.0"


class RegistrationError(Exception):
    pass


class CaptchaRejected(RegistrationError):
    pass


class DomainNotAllowed(RegistrationError):
    pass


class OtpError(Exception):
    pass


@dataclass
class IssuedSession:
    session_token: str
    device_selector: str
    device_validator: str
    user: User


def _audit(db: Session, *, action: str, actor_id=None, actor_type="user", target_type=None,
           target_id=None, ip=None, request_id=None, metadata=None) -> None:
    db.add(AuditEvent(actor_type=actor_type, actor_id=actor_id, action=action,
                      target_type=target_type, target_id=str(target_id) if target_id else None,
                      ip=ip, request_id=request_id, metadata_json=metadata))


class IdentityService:
    def __init__(self, db: Session, settings: Settings, mailer, captcha):
        self.db = db
        self.settings = settings
        self.mailer = mailer
        self.captcha = captcha

    # -- registration ----------------------------------------------------
    def register(self, *, profile: dict, agreement_text: str, captcha_token: str,
                 ip: str | None = None, user_agent: str | None = None) -> User:
        if not self.captcha.verify(captcha_token, action="register", remote_ip=ip):
            raise CaptchaRejected("captcha verification failed")

        email = profile["email"].strip().lower()
        allow = self.settings.domain_allow_list
        if allow and email.rsplit("@", 1)[-1] not in allow:
            raise DomainNotAllowed("email domain is not permitted to register")

        user = self.db.scalar(select(User).where(User.email == email))
        if user is None:
            user = User(**{**profile, "email": email})
            self.db.add(user)
            self.db.flush()
        elif user.status == "disabled":
            raise RegistrationError("account is disabled")

        self.db.add(AgreementAcceptance(
            user_id=user.id, agreement_version=AGREEMENT_VERSION,
            text_sha256=hashlib.sha256(agreement_text.encode()).digest(),
            ip=ip, user_agent=(user_agent or "")[:400]))

        self.issue_otp(email=email, purpose="registration", ip=ip)
        self._notify_team(user)
        _audit(self.db, action="registration.submitted", actor_id=user.id,
               target_type="user", target_id=user.id, ip=ip)
        self.db.flush()
        return user

    def _notify_team(self, user: User) -> None:
        lines = [f"{k}: {v}" for k, v in (
            ("Name", user.full_name), ("Designation", user.designation),
            ("Affiliation", user.affiliation), ("Institute", user.institute),
            ("Taluk", user.taluk), ("District", user.district), ("State", user.state),
            ("Country", user.country_iso2), ("Email", user.email), ("Phone", user.phone_e164),
            ("Project title", user.project_title), ("Project description", user.project_description),
            ("Purpose", user.purpose)) if v]
        self.mailer.send(to=self.settings.notify_addresses,
                         subject=f"EchoMiner registration: {user.full_name}",
                         text="A new EchoMiner registration was submitted.\n\n" + "\n".join(lines),
                         template="registration_notice")

    # -- OTP -------------------------------------------------------------
    def issue_otp(self, *, email: str, purpose: str = "registration", ip: str | None = None) -> None:
        email = email.strip().lower()
        active = self.db.scalar(
            select(OtpChallenge).where(OtpChallenge.email == email,
                                       OtpChallenge.locked_until.is_not(None),
                                       OtpChallenge.locked_until > now()))
        if active:
            raise OtpError("too many failed attempts; try again later")

        code = generate_otp(self.settings.otp_length)
        self.db.add(OtpChallenge(
            email=email, purpose=purpose,
            code_hash=hash_otp(code, self.settings.otp_pepper),
            expires_at=expires_in(self.settings.otp_ttl_seconds), request_ip=ip))
        minutes = self.settings.otp_ttl_seconds // 60
        self.mailer.send(
            to=[email], subject="EchoMiner Access Verification",
            text=(f"Your EchoMiner verification code is {code}\n\n"
                  f"It expires in {minutes} minutes and can be used once.\n"
                  "If you did not request access, ignore this message."),
            template="otp")

    def resend_otp(self, *, email: str, ip: str | None = None) -> None:
        """Resend / sign-in on a new device. Mail goes only to registered,
        enabled accounts; the caller always gets the same response, so this
        can neither enumerate accounts nor be used to mail arbitrary inboxes."""
        email = email.strip().lower()
        user = self.db.scalar(select(User).where(User.email == email))
        if user is None or user.status == "disabled":
            _audit(self.db, action="otp.resend_ignored", target_type="email", target_id=email[:64], ip=ip)
            return
        self.issue_otp(email=email, purpose="signin", ip=ip)

    def verify_otp(self, *, email: str, code: str, ip: str | None = None,
                   user_agent: str | None = None) -> IssuedSession:
        email = email.strip().lower()
        challenge = self.db.scalars(
            select(OtpChallenge)
            .where(OtpChallenge.email == email, OtpChallenge.consumed_at.is_(None))
            .order_by(OtpChallenge.created_at.desc())).first()

        if challenge is None or challenge.expires_at <= now():
            raise OtpError("invalid or expired code")
        if challenge.locked_until and challenge.locked_until > now():
            raise OtpError("invalid or expired code")

        if not verify_otp(code, challenge.code_hash, self.settings.otp_pepper):
            challenge.attempts += 1
            if challenge.attempts >= self.settings.otp_max_attempts:
                challenge.locked_until = expires_in(3600)
                _audit(self.db, action="otp.locked", target_type="email", target_id=email, ip=ip)
            # Commit, do not flush. The caller turns this into an HTTP error, and
            # the request-scoped session rolls back on exception -- which would
            # discard the attempt counter and make the lockout unenforceable.
            self.db.commit()
            raise OtpError("invalid or expired code")

        challenge.consumed_at = now()
        user = self.db.scalar(select(User).where(User.email == email))
        if user is None:
            raise OtpError("invalid or expired code")

        user.status = "active"
        user.email_verified_at = now()
        user.last_login_at = now()
        _audit(self.db, action="otp.verified", actor_id=user.id, target_type="user",
               target_id=user.id, ip=ip)
        return self._issue_session(user, ip=ip, user_agent=user_agent, new_device=True)

    # -- sessions & devices ----------------------------------------------
    def _issue_session(self, user: User, *, ip, user_agent, new_device: bool,
                       device: TrustedDevice | None = None) -> IssuedSession:
        token = new_token()
        self.db.add(SessionRow(
            user_id=user.id, token_hash=hash_token(token),
            absolute_expiry=expires_in(self.settings.session_absolute_seconds),
            ip=ip, user_agent=(user_agent or "")[:400]))

        # The selector is the device's stable lookup key; only the validator
        # rotates. Rotating the selector as well would make a stolen cookie
        # simply "not found" instead of "reused", and theft would go undetected.
        if new_device or device is None:
            selector, validator = new_device_pair()
            self.db.add(TrustedDevice(
                user_id=user.id, selector=selector,
                validator_hash=hash_token(validator),
                expires_at=expires_in(self.settings.trusted_device_days * 86400)))
        else:
            selector = device.selector
            _, validator = new_device_pair()
            device.validator_hash = hash_token(validator)
            device.last_seen_at = now()
        self.db.flush()
        return IssuedSession(session_token=token, device_selector=selector,
                             device_validator=validator, user=user)

    def restore_session(self, *, selector: str, validator: str, ip=None,
                        user_agent=None) -> Optional[IssuedSession]:
        """Silent re-auth on a known device. Rotates the validator on every use;
        presentation of a stale validator is treated as theft."""
        device = self.db.scalar(select(TrustedDevice).where(TrustedDevice.selector == selector))
        if device is None or device.revoked_at or device.expires_at <= now():
            return None

        if hash_token(validator) != device.validator_hash:
            self.revoke_all_devices(device.user_id, reason="validator_reuse")
            _audit(self.db, action="device.validator_reuse", actor_id=device.user_id,
                   target_type="device", target_id=device.id, ip=ip)
            # Committed for the same reason as the OTP lockout: this path ends in
            # a 401, and a rolled-back revocation would leave a stolen cookie live.
            self.db.commit()
            return None

        user = self.db.get(User, device.user_id)
        if user is None or user.status != "active":
            return None
        user.last_login_at = now()
        _audit(self.db, action="session.restored", actor_id=user.id, target_type="user",
               target_id=user.id, ip=ip)
        return self._issue_session(user, ip=ip, user_agent=user_agent, new_device=False, device=device)

    def revoke_all_devices(self, user_id, *, reason: str = "manual") -> int:
        devices = self.db.scalars(
            select(TrustedDevice).where(TrustedDevice.user_id == user_id,
                                        TrustedDevice.revoked_at.is_(None))).all()
        for d in devices:
            d.revoked_at = now()
        sessions = self.db.scalars(
            select(SessionRow).where(SessionRow.user_id == user_id,
                                     SessionRow.revoked_at.is_(None))).all()
        for s in sessions:
            s.revoked_at = now()
        _audit(self.db, action="device.revoke_all", actor_id=user_id,
               metadata={"reason": reason, "devices": len(devices)})
        return len(devices)

    def resolve_session(self, token: str) -> Optional[User]:
        row = self.db.scalar(select(SessionRow).where(SessionRow.token_hash == hash_token(token)))
        if row is None or row.revoked_at or row.absolute_expiry <= now():
            return None
        idle_cutoff = self.settings.session_idle_seconds
        if (now() - row.last_seen_at).total_seconds() > idle_cutoff:
            row.revoked_at = now()
            return None
        row.last_seen_at = now()
        return self.db.get(User, row.user_id)

    def sign_out(self, token: str) -> None:
        row = self.db.scalar(select(SessionRow).where(SessionRow.token_hash == hash_token(token)))
        if row and not row.revoked_at:
            row.revoked_at = now()
            _audit(self.db, action="session.signed_out", actor_id=row.user_id)
