"""Admin framework management routes with web UI."""
import json
import logging

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Request,
    status,
)
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies import get_current_user, get_db_session
from src.api.schemas import (
    AdminFrameworkResponse,
    FrameworkCreateWeb,
    FrameworkUpdateWeb,
)
from src.models.analysis_framework import AnalysisFramework
from src.models.scenario import Scenario
from src.models.user import User

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Admin Frameworks"])
templates = Jinja2Templates(directory="src/templates")


@router.get("/admin/frameworks", response_class=HTMLResponse)
async def list_all_frameworks_web(
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    """GET /admin/frameworks - Framework management page (Web UI)."""
    # Check admin role
    if user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin role required",
        )

    # Get all frameworks with usage count
    query = select(AnalysisFramework).order_by(
        AnalysisFramework.id.desc()
    )
    result = await db.execute(query)
    frameworks = result.scalars().all()

    # Get usage count for each framework
    framework_usage = {}
    for fw in frameworks:
        usage_query = (
            select(func.count(Scenario.id))
            .where(Scenario.framework_id == fw.id)
            .where(Scenario.deleted_at.is_(None))
        )
        count = await db.scalar(usage_query)
        framework_usage[fw.id] = count or 0

    return templates.TemplateResponse(
        "admin/frameworks.html",
        {
            "request": request,
            "user": user,
            "frameworks": frameworks,
            "framework_usage": framework_usage,
        },
    )


@router.post(
    "/admin/frameworks",
    response_model=AdminFrameworkResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_framework_web(
    framework_data: FrameworkCreateWeb,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    """POST /admin/frameworks - Create new framework (Web UI)."""
    # Check admin role
    if user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin role required",
        )

    # Check for duplicate name
    existing_query = select(AnalysisFramework).where(
        AnalysisFramework.name == framework_data.name
    )
    existing = await db.scalar(existing_query)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"프레임워크 '{framework_data.name}'이(가) 이미 존재합니다",
        )

    # Create framework
    new_framework = AnalysisFramework(
        name=framework_data.name,
        description=framework_data.description,
        labels_json=json.dumps(framework_data.labels),
    )

    db.add(new_framework)
    await db.commit()
    await db.refresh(new_framework)

    logger.info(
        f"Framework created: id={new_framework.id}, "
        f"name={new_framework.name}"
    )

    return new_framework


@router.put(
    "/admin/frameworks/{framework_id}",
    response_model=AdminFrameworkResponse,
)
async def update_framework_web(
    framework_id: int,
    framework_data: FrameworkUpdateWeb,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    """PUT /admin/frameworks/{id} - Update existing framework (Web UI)."""
    # Check admin role
    if user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin role required",
        )

    # Get framework
    framework = await db.get(AnalysisFramework, framework_id)
    if not framework:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="프레임워크를 찾을 수 없습니다",
        )

    # Check for duplicate name if updating name
    if (
        framework_data.name
        and framework_data.name != framework.name
    ):
        existing_query = select(AnalysisFramework).where(
            AnalysisFramework.name == framework_data.name
        )
        existing = await db.scalar(existing_query)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"프레임워크 '{framework_data.name}'이(가) 이미 존재합니다",
            )

    # Update fields
    if framework_data.name:
        framework.name = framework_data.name
    if framework_data.description:
        framework.description = framework_data.description
    if framework_data.labels:
        framework.labels_json = json.dumps(framework_data.labels)

    await db.commit()
    await db.refresh(framework)

    logger.info(f"Framework updated: id={framework_id}")

    return framework


@router.delete(
    "/admin/frameworks/{framework_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_framework_web(
    framework_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    """DELETE /admin/frameworks/{id} - Delete framework if not in use."""
    # Check admin role
    if user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin role required",
        )

    # Get framework
    framework = await db.get(AnalysisFramework, framework_id)
    if not framework:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="프레임워크를 찾을 수 없습니다",
        )

    # Check if framework is in use by any scenarios
    usage_query = (
        select(func.count(Scenario.id))
        .where(Scenario.framework_id == framework_id)
        .where(Scenario.deleted_at.is_(None))
    )
    usage_count = await db.scalar(usage_query)

    if usage_count and usage_count > 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"삭제할 수 없습니다: {usage_count}개의 시나리오가 이 프레임워크를 사용 중입니다",
        )

    # Delete framework
    await db.delete(framework)
    await db.commit()

    logger.info(
        f"Framework deleted: id={framework_id}, name={framework.name}"
    )

    return None
