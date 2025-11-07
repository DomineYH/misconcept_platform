"""프롬프트 템플릿 관리 서비스 (Task 3.2.2).

동적 프롬프트 로딩, 버전 관리, 5분 TTL 캐싱을 제공합니다.
StudentBot과 TutorBot이 DB 또는 파일 시스템에서
프롬프트를 로드할 수 있도록 지원합니다.
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.prompt_template import PromptTemplate

logger = logging.getLogger(__name__)


class PromptManager:
    """프롬프트 템플릿 관리 서비스.

    Features:
    - 활성 프롬프트 조회 (bot_type 기준)
    - 5분 TTL 캐싱 (<10ms 로드 시간)
    - Fallback: DB → 파일 시스템 → 하드코딩
    - 버전 관리 및 활성화/비활성화
    """

    # 캐시: {bot_type: (prompt_text, expires_at)}
    _cache: dict[str, tuple[str, datetime]] = {}
    _cache_ttl_seconds: int = 300  # 5분

    @classmethod
    async def get_active_prompt(cls, db: AsyncSession, bot_type: str) -> str:
        """활성 프롬프트 조회 (캐시 사용).

        Performance target: <10ms (cache hit), <50ms (cache miss)

        Args:
            db: Database session
            bot_type: 'student' or 'tutor'

        Returns:
            프롬프트 템플릿 문자열

        Fallback Priority:
            1. Cache (if valid)
            2. Database (active template)
            3. File system (src/prompts/{bot_type}_system.txt)
            4. Hardcoded default
        """
        # 1. 캐시 확인
        if bot_type in cls._cache:
            prompt, expires_at = cls._cache[bot_type]
            if datetime.now(timezone.utc) < expires_at:
                logger.debug(f"Cache hit: {bot_type} prompt (<10ms)")
                return prompt

        # 2. DB 조회
        try:
            result = await db.execute(
                select(PromptTemplate)
                .where(PromptTemplate.bot_type == bot_type)
                .where(PromptTemplate.is_active == True)  # noqa: E712
            )
            template = result.scalar_one_or_none()

            if template is not None:
                # 캐시 업데이트
                expires_at = datetime.now(timezone.utc) + timedelta(
                    seconds=cls._cache_ttl_seconds
                )
                cls._cache[bot_type] = (template.template_text, expires_at)
                logger.info(f"DB load: {bot_type} prompt v{template.version}")
                return template.template_text

        except Exception as e:
            logger.warning(
                f"DB query failed for {bot_type} prompt: {e}. "
                "Falling back to file system."
            )

        # 3. Fallback: 파일 시스템
        return cls._load_from_file(bot_type)

    @classmethod
    def _load_from_file(cls, bot_type: str) -> str:
        """파일 시스템에서 기본 프롬프트 로드.

        Args:
            bot_type: 'student' or 'tutor'

        Returns:
            프롬프트 문자열

        Fallback:
            파일이 없으면 하드코딩된 기본 프롬프트 반환
        """
        import os

        filename = f"src/prompts/{bot_type}_system.txt"

        if os.path.exists(filename):
            try:
                with open(filename, "r", encoding="utf-8") as f:
                    content = f.read()
                logger.info(f"File load: {bot_type} prompt from {filename}")
                return content
            except Exception as e:
                logger.error(f"Failed to read {filename}: {e}")

        # 4. 하드코딩된 fallback
        logger.warning(f"File not found: {filename}. Using hardcoded default.")
        return f"You are a {bot_type} bot."

    @classmethod
    async def list_prompts(
        cls, db: AsyncSession, bot_type: Optional[str] = None
    ) -> list[PromptTemplate]:
        """프롬프트 목록 조회 (버전 히스토리).

        Args:
            db: Database session
            bot_type: 필터링할 봇 타입 (None이면 전체)

        Returns:
            PromptTemplate 객체 리스트 (생성일 역순)
        """
        query = select(PromptTemplate)
        if bot_type:
            query = query.where(PromptTemplate.bot_type == bot_type)
        query = query.order_by(PromptTemplate.created_at.desc())

        result = await db.execute(query)
        return list(result.scalars().all())

    @classmethod
    async def create_prompt(
        cls,
        db: AsyncSession,
        bot_type: str,
        template_name: str,
        template_text: str,
        is_active: bool = False,
        updated_by: Optional[int] = None,
    ) -> PromptTemplate:
        """새 프롬프트 생성.

        Args:
            db: Database session
            bot_type: 'student' or 'tutor'
            template_name: 템플릿 이름
            template_text: 프롬프트 전문 (10-10,000자)
            is_active: 활성화 여부
            updated_by: 생성자 User ID

        Returns:
            생성된 PromptTemplate 객체
        """
        # 활성화 시 기존 활성 프롬프트 비활성화
        if is_active:
            await cls._deactivate_all(db, bot_type)

        # 버전 번호 계산 (동일 bot_type의 최대 버전 + 1)
        result = await db.execute(
            select(PromptTemplate)
            .where(PromptTemplate.bot_type == bot_type)
            .order_by(PromptTemplate.version.desc())
            .limit(1)
        )
        latest = result.scalar_one_or_none()
        version = (latest.version + 1) if latest else 1

        # 새 템플릿 생성
        template = PromptTemplate(
            bot_type=bot_type,
            template_name=template_name,
            template_text=template_text,
            version=version,
            is_active=is_active,
            updated_by=updated_by,
        )
        db.add(template)
        await db.flush()

        # 캐시 무효화
        if is_active:
            cls._invalidate_cache(bot_type)

        logger.info(
            f"Created prompt: {bot_type} v{version} " f"(active={is_active})"
        )

        return template

    @classmethod
    async def activate_prompt(
        cls, db: AsyncSession, prompt_id: int
    ) -> PromptTemplate:
        """프롬프트 활성화.

        동일 bot_type의 다른 프롬프트는 자동으로 비활성화됩니다.

        Args:
            db: Database session
            prompt_id: 활성화할 프롬프트 ID

        Returns:
            활성화된 PromptTemplate 객체
        """
        result = await db.execute(
            select(PromptTemplate).where(PromptTemplate.id == prompt_id)
        )
        template = result.scalar_one()

        # 동일 bot_type의 다른 프롬프트 비활성화
        await cls._deactivate_all(db, template.bot_type)

        # 활성화
        template.is_active = True
        template.updated_at = datetime.now(timezone.utc)
        await db.flush()

        # 캐시 무효화
        cls._invalidate_cache(template.bot_type)

        logger.info(
            f"Activated prompt: {template.bot_type} v{template.version}"
        )

        return template

    @classmethod
    async def _deactivate_all(cls, db: AsyncSession, bot_type: str) -> None:
        """특정 bot_type의 모든 활성 프롬프트 비활성화.

        Args:
            db: Database session
            bot_type: 'student' or 'tutor'
        """
        result = await db.execute(
            select(PromptTemplate)
            .where(PromptTemplate.bot_type == bot_type)
            .where(PromptTemplate.is_active == True)  # noqa: E712
        )
        for template in result.scalars().all():
            template.is_active = False
        await db.flush()

    @classmethod
    def _invalidate_cache(cls, bot_type: str) -> None:
        """캐시 무효화.

        Args:
            bot_type: 'student' or 'tutor'
        """
        if bot_type in cls._cache:
            del cls._cache[bot_type]
            logger.debug(f"Cache invalidated: {bot_type}")
