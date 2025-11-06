"""Authentication routes for login/logout."""
from fastapi import (
    APIRouter,
    Depends,
    Form,
    Request,
    Response,
    HTTPException,
    status,
)
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies import get_db_session
from src.models import User

router = APIRouter(tags=["Authentication"])
templates = Jinja2Templates(directory="src/templates")
limiter = Limiter(key_func=get_remote_address)


@router.get("/login", response_class=HTMLResponse)
async def get_login(request: Request):
    """Display login form."""
    return templates.TemplateResponse("login.html", {"request": request})


@router.post("/login")
@limiter.limit("5/minute")
async def post_login(
    request: Request,
    student_uid: str = Form(..., min_length=3, max_length=50),
    nickname: str = Form(..., min_length=2, max_length=30),
    db: AsyncSession = Depends(get_db_session),
):
    """Authenticate user and create session cookie."""
    # Validate student_uid format (alphanumeric + underscore)
    if not student_uid.replace("_", "").isalnum():
        raise HTTPException(
            status_code=400,
            detail="student_uid must be alphanumeric with underscores",
        )

    # Find or create user
    result = await db.execute(
        select(User).where(
            User.student_uid == student_uid, User.nickname == nickname
        )
    )
    user = result.scalar_one_or_none()

    if not user:
        # Create new user
        user = User(student_uid=student_uid, nickname=nickname)
        db.add(user)
        await db.commit()
        await db.refresh(user)

    # Create session cookie
    response = RedirectResponse(url="/scenarios", status_code=303)
    request.session["user_id"] = user.id
    request.session["student_uid"] = user.student_uid
    request.session["nickname"] = user.nickname

    return response


@router.post("/logout")
async def post_logout(request: Request):
    """Clear session and redirect to login."""
    request.session.clear()
    return RedirectResponse(url="/login", status_code=303)
