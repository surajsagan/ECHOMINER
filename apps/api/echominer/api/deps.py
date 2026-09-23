from typing import Annotated
from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session
from ..adapters.captcha import build_captcha
from ..adapters.mail import build_mailer
from ..config import Settings, get_settings
from ..db import get_db
from ..models import User
from ..services.identity import IdentityService

SESSION_COOKIE = "__Host-em_session"
DEVICE_COOKIE = "__Host-em_device"

_mailer_singleton = None
_captcha_singleton = None


def get_mailer(settings: Annotated[Settings, Depends(get_settings)]):
    global _mailer_singleton
    if _mailer_singleton is None:
        _mailer_singleton = build_mailer(settings)
    return _mailer_singleton


def get_captcha(settings: Annotated[Settings, Depends(get_settings)]):
    global _captcha_singleton
    if _captcha_singleton is None:
        _captcha_singleton = build_captcha(settings)
    return _captcha_singleton


def get_identity(db: Annotated[Session, Depends(get_db)],
                 settings: Annotated[Settings, Depends(get_settings)],
                 mailer=Depends(get_mailer), captcha=Depends(get_captcha)) -> IdentityService:
    return IdentityService(db, settings, mailer, captcha)


def client_ip(request: Request) -> str | None:
    forwarded = request.headers.get("cf-connecting-ip") or request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else None


def current_user(request: Request,
                 identity: Annotated[IdentityService, Depends(get_identity)]) -> User:
    token = request.cookies.get(SESSION_COOKIE)
    user = identity.resolve_session(token) if token else None
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "authentication required")
    return user
