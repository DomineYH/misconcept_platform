"""feedback_status == 'skipped' — brief-feedback box hidden, detail tabs intact.

Issue #55: when synthesis is skipped the report must NOT render any
brief-feedback / feedback box, while the level classification detail tabs
and the stat grid still render (the detail-tabs include condition is
`feedback_status != 'failed'`, which already lets 'skipped' through).
"""

import pytest
from jinja2 import Environment, FileSystemLoader


@pytest.fixture
def env():
    return Environment(loader=FileSystemLoader("src/templates"))


def _base_context(**overrides):
    ctx = {
        "request": None,
        "user": None,
        "session_id": 1,
        "distribution": {"Pressing": 1, "Linking": 0},
        "feedback": None,
        "feedback_sections": None,
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
        "is_admin": False,
        "stats": {
            "duration_seconds": 312,
            "teacher_question_count": 4,
            "student_response_count": 4,
            "tutor_intervention_count": 2,
        },
    }
    ctx.update(overrides)
    return ctx


def _skipped_context():
    return _base_context(feedback_status="skipped")


# ── analysis.html (full page) ──


class TestFullPageSkippedState:
    def test_no_brief_feedback_box(self, env):
        html = env.get_template("analysis.html").render(**_skipped_context())
        assert "analysis-brief-feedback" not in html

    def test_no_legacy_feedback_box(self, env):
        """skipped must NOT fall into the legacy else-branch."""
        html = env.get_template("analysis.html").render(**_skipped_context())
        assert "analysis-feedback" not in html

    def test_stat_grid_still_renders(self, env):
        html = env.get_template("analysis.html").render(**_skipped_context())
        assert "analysis-stat-grid" in html
        assert "analysis-stat-card" in html

    def test_detail_tabs_still_render(self, env):
        html = env.get_template("analysis.html").render(**_skipped_context())
        assert "analysis-detail-toggle" in html
        assert 'id="analysis-detail-panel"' in html

    def test_no_paragraph_text_leaks(self, env):
        """feedback == None 일 때 빈 박스조차 나오지 않아야 한다."""
        html = env.get_template("analysis.html").render(**_skipped_context())
        # 빈 <p></p> 조차 없어야 한다(박스 자체가 렌더링되지 않으므로)
        assert '<div class="analysis-brief-feedback">' not in html


# ── partials/analysis_modal.html ──


class TestModalSkippedState:
    def test_no_brief_feedback_box(self, env):
        html = env.get_template("partials/analysis_modal.html").render(
            **_skipped_context()
        )
        assert "analysis-brief-feedback" not in html

    def test_no_legacy_feedback_box(self, env):
        html = env.get_template("partials/analysis_modal.html").render(
            **_skipped_context()
        )
        assert "analysis-feedback" not in html

    def test_stat_grid_still_renders(self, env):
        html = env.get_template("partials/analysis_modal.html").render(
            **_skipped_context()
        )
        assert "analysis-stat-grid" in html

    def test_detail_tabs_still_render(self, env):
        html = env.get_template("partials/analysis_modal.html").render(
            **_skipped_context()
        )
        assert "analysis-detail-toggle" in html
