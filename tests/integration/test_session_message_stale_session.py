import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock, Mock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.models import Message, Scenario, Session, User
from src.services.session_lifecycle import StaleSessionError

STALE_SESSION_MESSAGE = (
    "세션이 종료되었거나 삭제되었습니다. 새로고침 후 다시 시도해주세요."
)


@pytest.fixture
async def route_test_session(
    db_session: AsyncSession,
    teacher_user: User,
    test_scenario: Scenario,
) -> Session:
    session = Session(
        teacher_id=teacher_user.id,
        scenario_id=test_scenario.id,
    )
    db_session.add(session)
    await db_session.commit()
    await db_session.refresh(session)
    return session


def _login_teacher(
    test_client: TestClient,
    teacher_user: User,
) -> dict[str, str]:
    login_response = test_client.post(
        "/login",
        data={
            "username": teacher_user.username,
            "password": "test1234",
        },
    )
    return dict(login_response.cookies)


async def test_post_message_returns_409_html_when_session_goes_stale(
    test_client: TestClient,
    db_session: AsyncSession,
    route_test_session: Session,
    teacher_user: User,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rollback_mock = AsyncMock(wraps=db_session.rollback)
    monkeypatch.setattr(db_session, "rollback", rollback_mock)
    manager = AsyncMock()
    manager.process_teacher_message.side_effect = StaleSessionError(
        session_id=route_test_session.id,
        reason="ended",
    )
    session_manager_factory = Mock(return_value=manager)
    monkeypatch.setattr(
        "src.api.routes.session_messages.SessionManager",
        session_manager_factory,
    )
    cookies = _login_teacher(test_client, teacher_user)

    response = test_client.post(
        f"/sessions/{route_test_session.id}/messages",
        data={"content": "분수 덧셈을 설명해볼래?"},
        cookies=cookies,
    )

    assert response.status_code == 409
    assert "text/html" in response.headers["content-type"]
    assert response.text == STALE_SESSION_MESSAGE
    assert response.headers.get("HX-Trigger") is None
    rollback_mock.assert_awaited_once()


async def test_post_message_returns_same_409_html_for_already_ended_session(
    test_client: TestClient,
    db_session: AsyncSession,
    route_test_session: Session,
    teacher_user: User,
) -> None:
    route_test_session.ended_at = datetime.now(timezone.utc)
    await db_session.commit()
    cookies = _login_teacher(test_client, teacher_user)

    response = test_client.post(
        f"/sessions/{route_test_session.id}/messages",
        data={"content": "분수 덧셈을 설명해볼래?"},
        cookies=cookies,
    )

    assert response.status_code == 409
    assert "text/html" in response.headers["content-type"]
    assert response.text == STALE_SESSION_MESSAGE
    assert response.headers.get("HX-Trigger") is None


async def test_post_message_returns_500_when_any_new_message_fails_to_render(
    test_client: TestClient,
    route_test_session: Session,
    teacher_user: User,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    created_at = datetime(2026, 1, 1, 9, 30, tzinfo=timezone.utc)
    teacher_message = Message(
        id=101,
        session_id=route_test_session.id,
        role="teacher",
        content="분수 덧셈을 설명해볼래?",
        created_at=created_at,
    )
    broken_message = Mock()
    broken_message.id = 102
    broken_message.role = "student"
    broken_message.content = "분모끼리 더하면 된다고 생각해요."
    manager = AsyncMock()
    manager.process_teacher_message.return_value = [
        teacher_message,
        broken_message,
    ]
    monkeypatch.setattr(
        "src.api.routes.session_messages.SessionManager",
        Mock(return_value=manager),
    )

    def fake_validate(message, request, templates, student_name=None):
        if message is broken_message:
            return None
        return '<div class="message message-teacher"></div>'

    monkeypatch.setattr(
        "src.api.routes.session_messages._validate_and_render_message",
        fake_validate,
    )
    cookies = _login_teacher(test_client, teacher_user)

    response = test_client.post(
        f"/sessions/{route_test_session.id}/messages",
        data={"content": "분수 덧셈을 설명해볼래?"},
        cookies=cookies,
    )

    assert response.status_code == 500
    assert response.headers.get("HX-Trigger") is None


async def test_post_message_normal_path_keeps_html_and_hx_trigger(
    test_client: TestClient,
    route_test_session: Session,
    teacher_user: User,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    created_at = datetime(2026, 1, 1, 9, 30, tzinfo=timezone.utc)
    teacher_message = Message(
        id=101,
        session_id=route_test_session.id,
        role="teacher",
        content="분수 덧셈을 설명해볼래?",
        created_at=created_at,
    )
    student_message = Message(
        id=102,
        session_id=route_test_session.id,
        role="student",
        content="분모끼리 더하면 된다고 생각해요.",
        created_at=created_at,
    )
    manager = AsyncMock()
    manager.process_teacher_message.return_value = [
        teacher_message,
        student_message,
    ]
    session_manager_factory = Mock(return_value=manager)
    monkeypatch.setattr(
        "src.api.routes.session_messages.SessionManager",
        session_manager_factory,
    )
    cookies = _login_teacher(test_client, teacher_user)

    response = test_client.post(
        f"/sessions/{route_test_session.id}/messages",
        data={"content": "분수 덧셈을 설명해볼래?"},
        cookies=cookies,
    )

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert 'class="message message-teacher"' in response.text
    assert 'class="message message-student"' in response.text
    assert "분수 덧셈을 설명해볼래?" in response.text
    assert "분모끼리 더하면 된다고 생각해요." in response.text

    trigger = response.headers.get("HX-Trigger")
    assert trigger is not None
    parsed_trigger = json.loads(trigger)
    assert parsed_trigger["messagesAdded"]["lastId"] == 102


async def test_post_message_propagates_unexpected_manager_exceptions(
    test_client: TestClient,
    route_test_session: Session,
    teacher_user: User,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manager = AsyncMock()
    manager.process_teacher_message.side_effect = RuntimeError(
        "unexpected manager failure"
    )
    session_manager_factory = Mock(return_value=manager)
    monkeypatch.setattr(
        "src.api.routes.session_messages.SessionManager",
        session_manager_factory,
    )
    cookies = _login_teacher(test_client, teacher_user)

    with pytest.raises(RuntimeError, match="unexpected manager failure"):
        test_client.post(
            f"/sessions/{route_test_session.id}/messages",
            data={"content": "테스트 메시지"},
            cookies=cookies,
        )
