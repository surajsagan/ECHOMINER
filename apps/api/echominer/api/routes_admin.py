"""Admin surface (M9/M10). Separate credential store, separate cookie, own idle timeout."""
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session

from ..config import Settings, get_settings
from ..db import get_db
from ..services.admin import ADMIN_SESSION_COOKIE, AdminAuthError, AdminService
from .deps import client_ip

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])


def get_admin_service(db: Annotated[Session, Depends(get_db)],
                      settings: Annotated[Settings, Depends(get_settings)]) -> AdminService:
    return AdminService(db, settings)


def current_admin(request: Request,
                  service: Annotated[AdminService, Depends(get_admin_service)]):
    token = request.cookies.get(ADMIN_SESSION_COOKIE)
    admin = service.resolve(token) if token else None
    if admin is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "administrator sign-in required")
    return admin


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    totp_code: Optional[str] = None


class ContentRequest(BaseModel):
    kind: str
    slug: str = Field(min_length=1, max_length=200)
    title: str = Field(min_length=1, max_length=400)
    body_md: str = ""
    link_url: Optional[str] = None
    published: bool = False
    sort_order: int = 0
    item_id: Optional[str] = None


@router.post("/auth/login")
def login(payload: LoginRequest, request: Request, response: Response,
          service: Annotated[AdminService, Depends(get_admin_service)],
          settings: Annotated[Settings, Depends(get_settings)]):
    try:
        token = service.login(email=payload.email, password=payload.password,
                              totp_code=payload.totp_code, ip=client_ip(request))
    except AdminAuthError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid credentials")
    response.set_cookie(ADMIN_SESSION_COOKIE, token, httponly=True,
                        secure=settings.env != "test", samesite="strict", path="/")
    return {"status": "signed_in"}


@router.delete("/auth/session")
def admin_sign_out(request: Request, response: Response,
                   service: Annotated[AdminService, Depends(get_admin_service)]):
    token = request.cookies.get(ADMIN_SESSION_COOKIE)
    if token:
        service.sign_out(token)
    response.delete_cookie(ADMIN_SESSION_COOKIE, path="/")
    return {"status": "signed_out"}


@router.get("/me")
def whoami(admin=Depends(current_admin)):
    return {"email": admin.email, "role": admin.role}


@router.get("/users")
def list_users(search: str | None = None, state: str | None = None, country: str | None = None,
               user_status: str | None = None, limit: int = 50, offset: int = 0,
               admin=Depends(current_admin),
               service: Annotated[AdminService, Depends(get_admin_service)] = None):
    return service.users(search=search, state=state, country=country,
                         status=user_status, limit=limit, offset=offset)


@router.get("/users.csv", response_class=PlainTextResponse)
def export_users(admin=Depends(current_admin),
                 service: Annotated[AdminService, Depends(get_admin_service)] = None):
    return PlainTextResponse(service.users_csv(), media_type="text/csv",
                             headers={"Content-Disposition": 'attachment; filename="echominer_users.csv"'})


@router.post("/users/{user_id}/status")
def set_status(user_id: str, payload: dict, admin=Depends(current_admin),
               service: Annotated[AdminService, Depends(get_admin_service)] = None):
    try:
        service.set_user_status(user_id, payload.get("status", ""))
    except KeyError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "user not found")
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc))
    return {"status": "updated"}


@router.get("/otp-logs")
def otp_logs(limit: int = 100, admin=Depends(current_admin),
             service: Annotated[AdminService, Depends(get_admin_service)] = None):
    return service.otp_log(limit)


@router.get("/email-logs")
def email_logs(limit: int = 100, admin=Depends(current_admin),
               service: Annotated[AdminService, Depends(get_admin_service)] = None):
    return service.email_log(limit)


@router.get("/analytics/usage")
def analytics_usage(days: int = 30, admin=Depends(current_admin),
                    service: Annotated[AdminService, Depends(get_admin_service)] = None):
    return {"summary": service.usage_summary(), "timeseries": service.timeseries(days)}


@router.get("/analytics/geo")
def analytics_geo(admin=Depends(current_admin),
                  service: Annotated[AdminService, Depends(get_admin_service)] = None):
    return service.geography()


@router.get("/analytics/projects")
def analytics_projects(admin=Depends(current_admin),
                       service: Annotated[AdminService, Depends(get_admin_service)] = None):
    return service.projects()


@router.get("/health")
def admin_health(admin=Depends(current_admin),
                 service: Annotated[AdminService, Depends(get_admin_service)] = None):
    return service.health()


@router.get("/audit")
def audit(limit: int = 100, admin=Depends(current_admin),
          service: Annotated[AdminService, Depends(get_admin_service)] = None):
    return service.audit(limit)


@router.get("/content/{kind}")
def list_content(kind: str, admin=Depends(current_admin),
                 service: Annotated[AdminService, Depends(get_admin_service)] = None):
    try:
        return service.content(kind)
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc))


@router.post("/content")
def save_content(payload: ContentRequest, admin=Depends(current_admin),
                 service: Annotated[AdminService, Depends(get_admin_service)] = None):
    try:
        return service.upsert_content(**payload.model_dump())
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc))


@router.delete("/content/{item_id}")
def remove_content(item_id: str, admin=Depends(current_admin),
                   service: Annotated[AdminService, Depends(get_admin_service)] = None):
    try:
        service.delete_content(item_id)
    except KeyError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "content item not found")
    return {"status": "deleted"}
