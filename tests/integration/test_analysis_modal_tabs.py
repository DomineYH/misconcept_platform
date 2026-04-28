"""Integration tests for Issue #33 — analysis detail 3-tab UI."""

from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.analysis_framework import AnalysisFramework
from src.models.message import Message
from src.models.question_analysis import QuestionAnalysis
from src.models.scenario import Scenario
from src.models.session import Session
from src.models.session_summary import SessionSummary
from src.models.user import User
from src.models.user_group import UserGroup


@pytest.fixture
async def leveled_framework(db_session: AsyncSession) -> AnalysisFramework:
    """Framework whose labels carry explicit high/low levels."""
    framework = AnalysisFramework(
        name="Leveled Framework",
        description="Test framework with levels",
        labels_json=json.dumps(
            [
                {"name": "Pressing", "criteria": "사고 탐색", "level": "high"},
                {"name": "Linking", "criteria": "연결 유도", "level": "high"},
                {"name": "Recall", "criteria": "단순 회상", "level": "low"},
                {"name": "Directing", "criteria": "방향 제시"},
            ]
        ),
    )
    db_session.add(framework)
    await db_session.commit()
    await db_session.refresh(framework)
    return framework


@pytest.fixture
async def leveled_scenario(
    db_session: AsyncSession,
    leveled_framework: AnalysisFramework,
    test_student_template,
    test_group: UserGroup,
) -> Scenario:
    scenario = Scenario(
        title="Leveled Scenario",
        prompt="prompt",
        student_profile="profile",
        framework_id=leveled_framework.id,
        student_template_id=test_student_template.id,
        is_active=1,
    )
    db_session.add(scenario)
    await db_session.commit()
    await db_session.refresh(scenario)
    return scenario


@pytest.fixture
async def teacher_user_local(
    db_session: AsyncSession, test_group: UserGroup
) -> User:
    user = User(
        username="teacher_tabs",
        nickname="탭 교사",
        role="teacher",
        group_id=test_group.id,
    )
    user.set_password("test1234")
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.fixture
async def seeded_analyzed_session(
    db_session: AsyncSession,
    teacher_user_local: User,
    leveled_scenario: Scenario,
) -> Session:
    """Seed a complete ended/analyzed session with mixed roles + grades."""
    started = datetime(2026, 1, 1, 10, 0, 0, tzinfo=timezone.utc)
    ended = datetime(2026, 1, 1, 10, 5, 0, tzinfo=timezone.utc)

    session = Session(
        teacher_id=teacher_user_local.id,
        scenario_id=leveled_scenario.id,
        started_at=started,
        ended_at=ended,
        tutor_intervention_count=0,
    )
    db_session.add(session)
    await db_session.commit()
    await db_session.refresh(session)

    msgs_data = [
        ("teacher", "왜 그렇게 생각하니?", "Pressing", "우수", 0.9),
        ("student", "분자끼리 더하면 돼요.", None, None, None),
        ("teacher", "정답이 뭐였더라?", "Recall", "개선", 0.7),
        ("tutor", "아주 좋은 시도네요.", None, None, None),
        ("teacher", "방법을 알려줄까?", "Directing", None, 0.5),
    ]
    seq = 0
    for role, content, label, grade, conf in msgs_data:
        m = Message(
            session_id=session.id,
            role=role,
            content=content,
            created_at=datetime(2026, 1, 1, 10, 0, seq, tzinfo=timezone.utc),
        )
        db_session.add(m)
        await db_session.flush()
        if label is not None:
            qa = QuestionAnalysis(
                message_id=m.id,
                label=label,
                grade=grade,
                confidence=conf,
                meta_json=json.dumps(
                    {
                        "summary": f"{label} 라벨 이유",
                        "improved_sentence": (
                            "더 깊이 생각해 보게 하는 질문은 어떨까?"
                            if grade == "개선"
                            else None
                        ),
                    }
                ),
            )
            db_session.add(qa)
        seq += 1

    db_session.add(
        SessionSummary(
            session_id=session.id,
            distribution_json=json.dumps(
                {"Pressing": 1, "Recall": 1, "Directing": 1}
            ),
            feedback="요약 피드백",
        )
    )
    await db_session.commit()
    return session


def _login(client: TestClient, username: str = "teacher_tabs"):
    resp = client.post(
        "/login",
        data={"username": username, "password": "test1234"},
    )
    assert resp.status_code in (200, 302, 303)
    return resp.cookies


async def test_get_analysis_includes_messages_with_levels(
    test_client: TestClient,
    seeded_analyzed_session: Session,
):
    """Issue #33: response includes messages timeline + framework map."""
    cookies = _login(test_client)
    resp = test_client.get(
        f"/sessions/{seeded_analyzed_session.id}/analysis",
        cookies=cookies,
    )
    assert resp.status_code == 200
    data = resp.json()

    assert "messages" in data
    msgs = data["messages"]
    # 3 teacher + 1 student + 1 tutor = 5 total
    assert len(msgs) == 5
    roles = [m["role"] for m in msgs]
    assert roles == ["teacher", "student", "teacher", "tutor", "teacher"]

    # teacher messages carry level mapping (high/low/None)
    teacher_levels = [m["level"] for m in msgs if m["role"] == "teacher"]
    assert teacher_levels == ["high", "low", None]

    # Framework criteria map present and populated
    assert "framework_label_criteria" in data
    fmap = data["framework_label_criteria"]
    assert fmap["Pressing"] == "사고 탐색"
    assert fmap["Recall"] == "단순 회상"


async def test_analysis_modal_renders_three_tabs(
    test_client: TestClient,
    seeded_analyzed_session: Session,
):
    """Issue #33: modal HTML includes 3 tabs and panels."""
    cookies = _login(test_client)
    resp = test_client.get(
        f"/sessions/{seeded_analyzed_session.id}/analysis_modal",
        cookies=cookies,
    )
    assert resp.status_code == 200
    html = resp.text

    assert html.count('role="tab"') == 3
    assert 'id="tab-coach"' in html
    assert 'id="tab-strong"' in html
    assert 'id="tab-improve"' in html
    assert 'id="panel-coach"' in html
    assert 'id="panel-strong"' in html
    assert 'id="panel-improve"' in html


async def test_analysis_modal_no_per_domain_boxes(
    test_client: TestClient,
    seeded_analyzed_session: Session,
):
    """Issue #33: legacy 영역별 박스가 어떤 분석 화면에도 남아있지 않다."""
    cookies = _login(test_client)
    modal_resp = test_client.get(
        f"/sessions/{seeded_analyzed_session.id}/analysis_modal",
        cookies=cookies,
    )
    page_resp = test_client.get(
        f"/sessions/{seeded_analyzed_session.id}/analysis_page",
        cookies=cookies,
    )
    assert modal_resp.status_code == 200
    assert page_resp.status_code == 200

    for html in (modal_resp.text, page_resp.text):
        assert "analysis-box pedagogical" not in html
        assert "analysis-box cognitive" not in html
        assert "analysis-box contextual" not in html
        assert "교육학적 분석" not in html
        assert "인지적 분석" not in html
        assert "맥락적 분석" not in html


async def test_improve_tab_shows_improved_sentence(
    test_client: TestClient,
    seeded_analyzed_session: Session,
):
    """Issue #33: 개선할 점 탭에 improved_sentence가 노출된다."""
    cookies = _login(test_client)
    resp = test_client.get(
        f"/sessions/{seeded_analyzed_session.id}/analysis_modal",
        cookies=cookies,
    )
    assert resp.status_code == 200
    html = resp.text
    assert "더 깊이 생각해 보게 하는 질문은 어떨까?" in html
    assert "개선한 문장" in html
