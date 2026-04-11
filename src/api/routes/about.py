"""Public About page route."""

import logging

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies import get_current_user, get_db_session, templates
from src.models.contributor import Contributor
from src.models.user import User

logger = logging.getLogger(__name__)

router = APIRouter(tags=["About"])


@router.get("/about", response_class=HTMLResponse)
async def about_page(
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    """GET /about - Public About page with contributor info."""
    result = await db.execute(
        select(Contributor).order_by(
            Contributor.sort_order, Contributor.id
        )
    )
    contributors = result.scalars().all()

    return templates.TemplateResponse(
        "about.html",
        {
            "request": request,
            "user": user,
            "contributors": contributors,
        },
    )
