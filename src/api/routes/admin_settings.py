"""Admin settings page — global analysis toggles."""

import logging

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies import get_admin_user, get_db_session, templates
from src.models.user import User
from src.services.app_settings import (
    is_synthesis_enabled,
    set_synthesis_enabled,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Admin Settings"])


@router.get("/admin/settings", response_class=HTMLResponse)
async def admin_settings_page(
    request: Request,
    user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db_session),
):
    """GET /admin/settings - 분석 설정 페이지."""
    synthesis_enabled = await is_synthesis_enabled(db)

    return templates.TemplateResponse(
        "admin/settings.html",
        {
            "request": request,
            "user": user,
            "synthesis_enabled": synthesis_enabled,
        },
    )


@router.post("/admin/settings/synthesis")
async def update_synthesis_setting(
    request: Request,
    synthesis_enabled: str = Form("false"),
    user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db_session),
):
    """POST /admin/settings/synthesis - 대화 서술형 분석 on/off 토글.

    폼 필드 `synthesis_enabled`는 "true"/"false" 문자열로 전달된다.
    HTML checkbox 단독 사용 시 체크 해제가 빈 값이 되므로,
    템플릿에서 숨겨진 입력 + 체크박스 조합으로 "true"/"false"를
    명시적으로 보낸다.
    """
    enabled = synthesis_enabled.strip().lower() == "true"
    await set_synthesis_enabled(db, enabled)

    return RedirectResponse(url="/admin/settings", status_code=303)
