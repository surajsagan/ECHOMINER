"""Public content surface (M10). Published items only."""
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from ..config import Settings, get_settings
from ..db import get_db
from ..services.admin import AdminService

router = APIRouter(prefix="/api/v1/content", tags=["content"])

ALIASES = {"news": "news", "publications": "publication", "faqs": "faq"}


@router.get("/{kind}")
def public_content(kind: str, response: Response,
                   db: Annotated[Session, Depends(get_db)],
                   settings: Annotated[Settings, Depends(get_settings)]):
    internal = ALIASES.get(kind)
    if internal is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "unknown content type")
    response.headers["Cache-Control"] = "public, max-age=300"
    return AdminService(db, settings).content(internal, published_only=True)
