"""Security: Jinja2 autoescape neutralises XSS in synthesis."""

import pytest
from jinja2 import Environment, FileSystemLoader


@pytest.fixture
def env():
    return Environment(
        loader=FileSystemLoader("src/templates"),
        autoescape=True,
    )


def _base_context(**overrides):
    ctx = {
        "request": None,
        "user": None,
        "session_id": 1,
        "distribution": {"Pressing": 1, "Linking": 0},
        "feedback": "Plain text <script>alert(1)</script>",
        "questions": [],
        "session_ended_at": "2026-01-01T01:00:00",
        "is_admin": False,
    }
    ctx.update(overrides)
    return ctx


class TestXSSInSynthesisPayload:
    """Verify Jinja2 autoescape sanitises user-controlled feedback strings."""

    def test_brief_feedback_xss_escaped_modal(self, env):
        """brief_feedback list entries with script tags must be escaped."""
        ctx = _base_context(
            feedback_status="ok",
            feedback_sections={
                "brief_feedback": ["<script>alert(1)</script>"],
            },
            stats={
                "duration_seconds": 60,
                "teacher_question_count": 1,
                "student_response_count": 1,
                "tutor_intervention_count": 0,
            },
        )
        html = env.get_template("partials/analysis_modal.html").render(**ctx)
        assert "&lt;script&gt;" in html
        assert "<script>alert(1)</script>" not in html

    def test_plain_feedback_xss_escaped_modal(self, env):
        """Legacy/failed feedback string with script tags must be escaped."""
        ctx = _base_context(
            feedback_status="legacy",
            feedback_sections=None,
            stats={
                "duration_seconds": 60,
                "teacher_question_count": 1,
                "student_response_count": 1,
                "tutor_intervention_count": 0,
            },
        )
        html = env.get_template("partials/analysis_modal.html").render(**ctx)
        assert "&lt;script&gt;" in html
        assert "<script>alert(1)</script>" not in html

    def test_brief_feedback_xss_escaped_full_page(self, env):
        """Full-page template must also escape brief_feedback."""
        ctx = _base_context(
            feedback_status="ok",
            feedback_sections={
                "brief_feedback": ["<script>alert(1)</script>"],
            },
            stats={
                "duration_seconds": 60,
                "teacher_question_count": 1,
                "student_response_count": 1,
                "tutor_intervention_count": 0,
            },
        )
        ctx["user"] = type("U", (), {"nickname": "T", "role": "teacher"})()
        html = env.get_template("analysis.html").render(**ctx)
        assert "&lt;script&gt;" in html
        assert "<script>alert(1)</script>" not in html
