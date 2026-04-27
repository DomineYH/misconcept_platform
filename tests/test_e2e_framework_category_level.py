"""End-to-end tests for framework category_name + label level + grade display.

Validates:
- Round-trip of category_name and label level through the Admin API
- QuestionAnalysis.grade populated from framework labels_grade_map
- Grade snapshot semantics (past grade unchanged after framework update)
"""

import json
from datetime import datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.analysis_framework import AnalysisFramework
from src.models.message import Message
from src.models.question_analysis import QuestionAnalysis
from src.models.scenario import Scenario
from src.models.session import Session
from src.models.session_summary import SessionSummary
from src.models.user import User

# noqa: I001 — isort disagrees but project convention groups stdlib/Third-party/first-party separately


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
async def admin_client(
    async_client: AsyncClient,
    test_admin: User,
) -> AsyncClient:
    """Async client authenticated as admin."""
    await async_client.post(
        "/login",
        data={"username": test_admin.username, "password": "test1234"},
    )
    return async_client


@pytest.fixture
async def fresh_framework(async_db_session: AsyncSession) -> AnalysisFramework:
    """Create a framework with category_name and levelled labels."""
    fw = AnalysisFramework(
        name="질문 품질 분석",
        description="프레임워크 카테고리 + 라벨 수준 테스트",
        category_name="질문 품질",
        labels_json=json.dumps(
            [
                {
                    "name": "개방형 질문",
                    "criteria": "학생의 사고를 유도하는 질문",
                    "level": "high",
                },
                {
                    "name": "폐쇄형 질문",
                    "criteria": "단답형 응답을 유도하는 질문",
                    "level": "low",
                },
            ],
            ensure_ascii=False,
        ),
    )
    async_db_session.add(fw)
    await async_db_session.flush()
    return fw


# ---------------------------------------------------------------------------
# Test: category_name + level round-trip via Admin API
# ---------------------------------------------------------------------------


class TestFrameworkCategoryLevelRoundTrip:
    """category_name and label level survive Admin API create/update cycle."""

    @pytest.mark.asyncio
    async def test_create_framework_with_category_and_levels(
        self,
        admin_client: AsyncClient,
        async_db_session: AsyncSession,
    ):
        """POST /admin/frameworks creates framework with category + levels."""
        payload = {
            "name": "카테고리 프레임워크",
            "description": "라벨 수준 테스트",
            "category_name": "질문 분류",
            "labels": [
                {"name": "탐색형", "criteria": "탐색", "level": "high"},
                {"name": "확인형", "criteria": "확인", "level": "low"},
            ],
        }
        resp = await admin_client.post(
            "/admin/frameworks",
            json=payload,
        )
        assert resp.status_code == 201, resp.text

        data = resp.json()
        assert data["category_name"] == "질문 분류"
        labels = json.loads(data["labels_json"])
        assert labels[0]["level"] == "high"
        assert labels[1]["level"] == "low"

    @pytest.mark.asyncio
    async def test_update_framework_category_and_levels(
        self,
        admin_client: AsyncClient,
        fresh_framework: AnalysisFramework,
    ):
        """POST /admin/frameworks/{id}/update updates category + levels."""
        payload = {
            "category_name": "수정된 카테고리",
            "labels": [
                {"name": "개방형 질문", "criteria": "탐색", "level": "high"},
                {"name": "폐쇄형 질문", "criteria": "확인", "level": "low"},
            ],
        }
        resp = await admin_client.post(
            f"/admin/frameworks/{fresh_framework.id}/update",
            json=payload,
        )
        assert resp.status_code == 200, resp.text

        data = resp.json()
        assert data["category_name"] == "수정된 카테고리"

    @pytest.mark.asyncio
    async def test_read_framework_includes_category_and_levels(
        self,
        async_db_session: AsyncSession,
        fresh_framework: AnalysisFramework,
    ):
        """Framework ORM object includes category_name + levels."""
        result = await async_db_session.execute(
            select(AnalysisFramework).where(
                AnalysisFramework.id == fresh_framework.id
            )
        )
        fw = result.scalar_one()
        assert fw.category_name == "질문 품질"
        assert fw.labels_grade_map["개방형 질문"] == "우수"
        assert fw.labels_grade_map["폐쇄형 질문"] == "개선"


# ---------------------------------------------------------------------------
# Test: grade population in QuestionAnalysis
# ---------------------------------------------------------------------------


class TestGradePopulation:
    """QuestionAnalysis.grade is populated from framework labels_grade_map."""

    @pytest.mark.asyncio
    async def test_grade_high_produces_excellent(
        self,
        async_db_session: AsyncSession,
        fresh_framework: AnalysisFramework,
        test_teacher: User,
    ):
        """Question classified as high-level label gets grade='우수'."""
        grade_map = fresh_framework.labels_grade_map
        assert grade_map["개방형 질문"] == "우수"

        # Create session + message + analysis with grade
        scenario = Scenario(
            title="Test",
            prompt="p",
            student_profile="sp",
            framework_id=fresh_framework.id,
            is_active=1,
        )
        async_db_session.add(scenario)
        await async_db_session.flush()

        session = Session(
            scenario_id=scenario.id,
            teacher_id=test_teacher.id,
        )
        async_db_session.add(session)
        await async_db_session.flush()

        msg = Message(
            session_id=session.id,
            role="teacher",
            content="왜 그렇게 생각해?",
        )
        async_db_session.add(msg)
        await async_db_session.flush()

        qa = QuestionAnalysis(
            message_id=msg.id,
            label="개방형 질문",
            confidence=0.9,
            grade="우수",
        )
        async_db_session.add(qa)
        await async_db_session.flush()

        # Verify grade persisted
        result = await async_db_session.execute(
            select(QuestionAnalysis).where(
                QuestionAnalysis.message_id == msg.id
            )
        )
        saved_qa = result.scalar_one()
        assert saved_qa.grade == "우수"

    @pytest.mark.asyncio
    async def test_grade_low_produces_improve(
        self,
        async_db_session: AsyncSession,
        fresh_framework: AnalysisFramework,
    ):
        """Framework grade_map maps low-level label to '개선'."""
        grade_map = fresh_framework.labels_grade_map
        assert grade_map["폐쇄형 질문"] == "개선"


# ---------------------------------------------------------------------------
# Test: grade snapshot semantics
# ---------------------------------------------------------------------------


class TestGradeSnapshotSemantics:
    """Changing framework level does NOT retroactively change past grades."""

    @pytest.mark.asyncio
    async def test_past_grade_unchanged_after_framework_update(
        self,
        async_db_session: AsyncSession,
        fresh_framework: AnalysisFramework,
        test_teacher: User,
    ):
        """After changing label level from high→low, past QA.grade stays."""
        # 1. Create analysis with grade='우수' (high)
        scenario = Scenario(
            title="Snapshot test",
            prompt="p",
            student_profile="sp",
            framework_id=fresh_framework.id,
            is_active=1,
        )
        async_db_session.add(scenario)
        await async_db_session.flush()

        session = Session(
            scenario_id=scenario.id,
            teacher_id=test_teacher.id,
        )
        async_db_session.add(session)
        await async_db_session.flush()

        msg = Message(
            session_id=session.id,
            role="teacher",
            content="무엇인가요?",
        )
        async_db_session.add(msg)
        await async_db_session.flush()

        qa = QuestionAnalysis(
            message_id=msg.id,
            label="개방형 질문",
            confidence=0.85,
            grade="우수",
        )
        async_db_session.add(qa)
        await async_db_session.flush()

        # 2. Update framework: change level high→low
        fresh_framework.labels_json = json.dumps(
            [
                {
                    "name": "개방형 질문",
                    "criteria": "학생의 사고를 유도하는 질문",
                    "level": "low",
                },
                {
                    "name": "폐쇄형 질문",
                    "criteria": "단답형 응답을 유도하는 질문",
                    "level": "high",
                },
            ],
            ensure_ascii=False,
        )
        await async_db_session.flush()

        # 3. Verify past grade is still '우수'
        await async_db_session.refresh(qa)
        assert qa.grade == "우수", (
            "Past grade should be snapshot, not re-derived from framework"
        )

        # 4. Verify the framework's grade_map now reflects the update
        assert fresh_framework.labels_grade_map["개방형 질문"] == "개선"


# ---------------------------------------------------------------------------
# Test: analysis route includes grade + grade_counts
# ---------------------------------------------------------------------------


class TestAnalysisRouteGradeData:
    """Analysis API returns grade per question and grade_counts summary."""

    @pytest.mark.asyncio
    async def test_analysis_json_includes_grade(
        self,
        async_client: AsyncClient,
        async_db_session: AsyncSession,
        test_teacher: User,
        test_scenario,
    ):
        """GET /sessions/{id}/analysis includes grade + grade_counts."""
        # Create a session with ended_at set
        session = Session(
            scenario_id=test_scenario.id,
            teacher_id=test_teacher.id,
            started_at=datetime.utcnow() - timedelta(hours=1),
            ended_at=datetime.utcnow(),
        )
        async_db_session.add(session)
        await async_db_session.flush()

        msg = Message(
            session_id=session.id,
            role="teacher",
            content="왜 그렇게 생각해?",
        )
        async_db_session.add(msg)
        await async_db_session.flush()

        qa = QuestionAnalysis(
            message_id=msg.id,
            label="Pressing",
            confidence=0.9,
            grade="우수",
        )
        async_db_session.add(qa)

        summary = SessionSummary(
            session_id=session.id,
            distribution_json='{"Pressing":1}',
            feedback="Good",
        )
        async_db_session.add(summary)
        await async_db_session.flush()

        # Login
        await async_client.post(
            "/login",
            data={"username": test_teacher.username, "password": "test1234"},
        )

        resp = await async_client.get(f"/sessions/{session.id}/analysis")
        assert resp.status_code == 200
        data = resp.json()

        # Check questions include grade
        assert len(data["questions"]) == 1
        assert data["questions"][0]["grade"] == "우수"

        # Check grade_counts
        assert data["grade_counts"]["우수"] == 1
        assert data["grade_counts"]["개선"] == 0
