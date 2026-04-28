"""Template tests: analysis.html full-page wedge parity."""

import pytest
from jinja2 import Environment, FileSystemLoader


@pytest.fixture
def env():
    return Environment(loader=FileSystemLoader("src/templates"))


class _User:
    nickname = "TestUser"
    role = "teacher"


_STATS = {
    "duration_seconds": 312,
    "teacher_question_count": 4,
    "student_response_count": 4,
    "tutor_intervention_count": 2,
}


def _base_context(**overrides):
    ctx = {
        "request": None,
        "user": _User(),
        "session_id": 1,
        "distribution": {"Pressing": 1, "Linking": 0},
        "feedback": "Good questioning technique.",
        "questions": [
            {
                "content": "How did you solve this?",
                "label": "Pressing",
                "confidence": 0.85,
                "reasoning": None,
                "created_at": "2026-01-01T00:00:00",
            }
        ],
        "session_ended_at": "2026-01-01T01:00:00",
    }
    ctx.update(overrides)
    return ctx


def _render(env, **overrides):
    template = env.get_template("analysis.html")
    return template.render(**_base_context(**overrides))


def _ok_ctx(brief=("좋은 출발!",)):
    return dict(
        feedback_status="ok",
        feedback_sections={"brief_feedback": list(brief)},
        stats=_STATS,
    )


class TestFullPageWedgeParity:
    """analysis.html must contain same wedge elements as modal."""

    def test_has_wedge_container(self, env):
        html = _render(env, **_ok_ctx())
        assert "analysis-wedge" in html

    def test_has_data_session_id(self, env):
        html = _render(env, **_ok_ctx())
        assert 'data-session-id="1"' in html

    def test_ok_state_shows_brief_feedback(self, env):
        html = _render(
            env,
            **_ok_ctx(brief=("좋은 출발이었어요!",)),
        )
        assert "analysis-brief-feedback" in html
        assert "좋은 출발이었어요!" in html

    def test_stat_grid_present(self, env):
        html = _render(env, **_ok_ctx())
        assert "analysis-stat-grid" in html
        assert "analysis-stat-card" in html

    def test_stat_values_render(self, env):
        html = _render(env, **_ok_ctx())
        assert ">5<" in html
        assert "분" in html
        assert ">12<" in html
        assert "초" in html

    def test_toggle_button_present(self, env):
        html = _render(env, **_ok_ctx())
        assert "analysis-detail-toggle" in html
        assert 'aria-expanded="false"' in html
        assert "상세 분석" in html

    def test_detail_panel_hidden(self, env):
        html = _render(env, **_ok_ctx())
        assert 'id="analysis-detail-panel"' in html
        idx = html.index('id="analysis-detail-panel"')
        assert "hidden" in html[idx : idx + 80]

    def test_failed_state_no_toggle(self, env):
        html = _render(
            env,
            feedback_status="failed",
            feedback_sections=None,
            stats=_STATS,
        )
        assert "analysis-detail-toggle" not in html
        assert "analysis-brief-feedback" not in html

    def test_legacy_state_shows_plain_feedback(self, env):
        html = _render(
            env,
            feedback_status="legacy",
            feedback_sections=None,
            stats=_STATS,
        )
        assert "analysis-feedback" in html
        assert "Good questioning technique." in html

    def test_uses_dl_semantic(self, env):
        html = _render(env, **_ok_ctx())
        assert "<dl" in html
        assert "<dt" in html
        assert "<dd" in html

    def test_aria_labels(self, env):
        html = _render(env, **_ok_ctx())
        assert 'aria-label="대화 시간 5분 12초"' in html
        assert 'aria-label="선생님 질문 4개"' in html
