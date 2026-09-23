"""Auth surface. Responses are deliberately uniform so registration state cannot
be probed by an unauthenticated caller."""
from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from ..config import Settings, get_settings
from ..services.identity import (CaptchaRejected, DomainNotAllowed, IdentityService,
                                 OtpError, RegistrationError)
from .deps import DEVICE_COOKIE, SESSION_COOKIE, client_ip, current_user, get_identity
from .schemas import (MeResponse, OtpResendRequest, OtpVerifyRequest, RegistrationRequest,
                      RegistrationResponse)

router = APIRouter(prefix="/api/v1", tags=["auth"])


def _set_cookies(response: Response, settings: Settings, session_token: str,
                 selector: str, validator: str) -> None:
    # __Host- cookies are rejected by browsers unless Secure. Browsers treat
    # http://localhost as secure, so dev keeps the flag too; only the test
    # client (plain http://testserver) runs without it.
    secure = settings.env != "test"
    response.set_cookie(SESSION_COOKIE, session_token, httponly=True, secure=secure,
                        samesite="lax", path="/", max_age=settings.session_absolute_seconds)
    response.set_cookie(DEVICE_COOKIE, f"{selector}:{validator}", httponly=True, secure=secure,
                        samesite="lax", path="/", max_age=settings.trusted_device_days * 86400)


@router.post("/registrations", response_model=RegistrationResponse, status_code=status.HTTP_202_ACCEPTED)
def register(payload: RegistrationRequest, request: Request,
             identity: Annotated[IdentityService, Depends(get_identity)]):
    profile = payload.model_dump(exclude={"agreement_accepted", "agreement_text", "captcha_token"})
    try:
        identity.register(profile=profile, agreement_text=payload.agreement_text,
                          captcha_token=payload.captcha_token, ip=client_ip(request),
                          user_agent=request.headers.get("user-agent"))
    except CaptchaRejected:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "captcha verification failed")
    except DomainNotAllowed:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "this email domain cannot register")
    except OtpError as exc:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, str(exc))
    except RegistrationError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc))
    return RegistrationResponse(status="verification_sent", email=payload.email)


@router.post("/auth/otp/resend", status_code=status.HTTP_202_ACCEPTED)
def resend(payload: OtpResendRequest, request: Request,
           identity: Annotated[IdentityService, Depends(get_identity)],
           captcha=Depends(lambda i=Depends(get_identity): i.captcha)):
    if not identity.captcha.verify(payload.captcha_token, action="resend", remote_ip=client_ip(request)):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "captcha verification failed")
    try:
        identity.resend_otp(email=payload.email, ip=client_ip(request))
    except OtpError as exc:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, str(exc))
    return {"status": "verification_sent"}


@router.post("/auth/otp/verify")
def verify(payload: OtpVerifyRequest, request: Request, response: Response,
           identity: Annotated[IdentityService, Depends(get_identity)],
           settings: Annotated[Settings, Depends(get_settings)]):
    try:
        issued = identity.verify_otp(email=payload.email, code=payload.code,
                                     ip=client_ip(request),
                                     user_agent=request.headers.get("user-agent"))
    except OtpError:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "invalid or expired code")
    _set_cookies(response, settings, issued.session_token, issued.device_selector, issued.device_validator)
    return {"status": "verified", "tool_unlocked": True}


@router.post("/auth/session/restore")
def restore(request: Request, response: Response,
            identity: Annotated[IdentityService, Depends(get_identity)],
            settings: Annotated[Settings, Depends(get_settings)]):
    raw = request.cookies.get(DEVICE_COOKIE, "")
    if ":" not in raw:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "no trusted device")
    selector, validator = raw.split(":", 1)
    issued = identity.restore_session(selector=selector, validator=validator,
                                      ip=client_ip(request),
                                      user_agent=request.headers.get("user-agent"))
    if issued is None:
        response.delete_cookie(DEVICE_COOKIE, path="/")
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "verification required")
    _set_cookies(response, settings, issued.session_token, issued.device_selector, issued.device_validator)
    return {"status": "restored", "tool_unlocked": True}


@router.delete("/auth/session")
def sign_out(request: Request, response: Response,
             identity: Annotated[IdentityService, Depends(get_identity)]):
    token = request.cookies.get(SESSION_COOKIE)
    if token:
        identity.sign_out(token)
    response.delete_cookie(SESSION_COOKIE, path="/")
    return {"status": "signed_out"}


@router.get("/me", response_model=MeResponse)
def me(user=Depends(current_user)):
    return user
