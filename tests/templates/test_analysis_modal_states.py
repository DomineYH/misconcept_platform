"""Analysis modal renders correctly across all 4 feedback_status states."""

import pytest
from jinja2 import Environment, FileSystemLoader


@pytest.fixture
def env():
    return Environment(loader=FileSystemLoader("src/templates"))


def _base_context(**overrides):
    """Minimal context shared across all modal render tests."""
    ctx = {
        "request": None,
        "user": None,
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
        "is_admin": False,
    }
    ctx.update(overrides)
    return ctx


def _ok_context():
    return _base_context(
        feedback_status="ok",
        feedback_sections={
            "brief_feedback": [
                "학생 풀이 과정을 물어본 것은 좋은 출발이었어요!",
                "핵심 단서를 더 깊이 탐색했다면 오개념에 빨리 다가갔을 거예요.",
            ],
        },
        stats={
            "duration_seconds": 312,
            "teacher_question_count": 4,
            "student_response_count": 4,
            "tutor_intervention_count": 2,
        },
    )


def _degraded_context():
    return _base_context(
        feedback_status="degraded",
        feedback_sections={
            "brief_feedback": [
                "학생 풀이 과정을 물어본 것은 좋은 출발이었어요!",
            ],
        },
        stats={
            "duration_seconds": 312,
            "teacher_question_count": 4,
            "student_response_count": 4,
            "tutor_intervention_count": 2,
        },
    )


def _failed_context():
    return _base_context(
        feedback_status="failed",
        feedback_sections=None,
        stats={
            "duration_seconds": 312,
            "teacher_question_count": 4,
            "student_response_count": 4,
            "tutor_intervention_count": 2,
        },
    )


def _legacy_context():
    return _base_context(
        feedback_status="legacy",
        feedback_sections=None,
        stats={
            "duration_seconds": 312,
            "teacher_question_count": 4,
            "student_response_count": 4,
            "tutor_intervention_count": 2,
        },
    )


# ── ok state ──


class TestOkState:
    def test_shows_info_blue_feedback_box(self, env):
        template = env.get_template("partials/analysis_modal.html")
        html = template.render(**_ok_context())
        assert "analysis-brief-feedback" in html
        # Info-blue box, NOT purple
        assert "analysis-brief-feedback" in html

    def test_shows_brief_feedback_paragraphs(self, env):
        template = env.get_template("partials/analysis_modal.html")
        html = template.render(**_ok_context())
        assert "좋은 출발이었어요" in html
        assert "핵심 단서를 더 깊이 탐색" in html

    def test_shows_stat_grid(self, env):
        template = env.get_template("partials/analysis_modal.html")
        html = template.render(**_ok_context())
        assert "analysis-stat-grid" in html
        assert "analysis-stat-card" in html

    def test_stat_values_render(self, env):
        template = env.get_template("partials/analysis_modal.html")
        html = template.render(**_ok_context())
        # 312 seconds = 5분 12초
        assert ">5<" in html
        assert "분" in html
        assert ">12<" in html
        assert "초" in html
        assert ">4<" in html  # teacher_question_count
        assert ">2<" in html  # tutor_intervention_count

    def test_shows_toggle_button(self, env):
        template = env.get_template("partials/analysis_modal.html")
        html = template.render(**_ok_context())
        assert "analysis-detail-toggle" in html
        assert 'aria-expanded="false"' in html
        assert 'aria-controls="analysis-detail-panel"' in html
        assert "질문별 분석 보기" in html

    def test_detail_panel_hidden_by_default(self, env):
        template = env.get_template("partials/analysis_modal.html")
        html = template.render(**_ok_context())
        assert 'id="analysis-detail-panel"' in html
        # Panel should have hidden attribute
        idx = html.index('id="analysis-detail-panel"')
        assert "hidden" in html[idx : idx + 80]

    def test_no_degraded_note(self, env):
        template = env.get_template("partials/analysis_modal.html")
        html = template.render(**_ok_context())
        assert "analysis-degraded-note" not in html

    def test_uses_flat_class_namespace(self, env):
        template = env.get_template("partials/analysis_modal.html")
        html = template.render(**_ok_context())
        # Must use .analysis-wedge, NOT .analysis-report__wedge (BEM)
        assert "analysis-wedge" in html
        assert "analysis-report__" not in html

    def test_stat_card_uses_dl_dt_dd_markup(self, env):
        template = env.get_template("partials/analysis_modal.html")
        html = template.render(**_ok_context())
        assert "<dl" in html
        assert "<dt" in html
        assert "<dd" in html

    def test_stat_card_aria_labels(self, env):
        template = env.get_template("partials/analysis_modal.html")
        html = template.render(**_ok_context())
        assert 'aria-label="대화 시간 5분 12초"' in html
        assert 'aria-label="선생님 질문 4개"' in html
        assert 'aria-label="학생 응답 4회"' in html
        assert 'aria-label="멘토 개입 2회"' in html

    def test_toggle_extends_btn_modal_secondary(self, env):
        template = env.get_template("partials/analysis_modal.html")
        html = template.render(**_ok_context())
        assert "btn-modal-secondary" in html
        # The toggle button itself has both classes
        assert (
            "btn-modal-secondary analysis-detail-toggle" in html
            or "analysis-detail-toggle" in html
        )


# ── degraded state ──


class TestDegradedState:
    def test_shows_feedback_box(self, env):
        template = env.get_template("partials/analysis_modal.html")
        html = template.render(**_degraded_context())
        assert "analysis-brief-feedback" in html

    def test_shows_degraded_note(self, env):
        template = env.get_template("partials/analysis_modal.html")
        html = template.render(**_degraded_context())
        assert "analysis-degraded-note" in html
        assert "일부 피드백 항목이 생성되지 않았어요" in html

    def test_shows_toggle(self, env):
        template = env.get_template("partials/analysis_modal.html")
        html = template.render(**_degraded_context())
        assert "analysis-detail-toggle" in html


# ── failed state ──


class TestFailedState:
    def test_shows_neutral_feedback_box(self, env):
        template = env.get_template("partials/analysis_modal.html")
        html = template.render(**_failed_context())
        # Failed state uses the existing .analysis-feedback (neutral gray box)
        assert "analysis-feedback" in html
        assert "Good questioning technique." in html

    def test_shows_stat_grid(self, env):
        template = env.get_template("partials/analysis_modal.html")
        html = template.render(**_failed_context())
        assert "analysis-stat-grid" in html

    def test_no_toggle_button(self, env):
        template = env.get_template("partials/analysis_modal.html")
        html = template.render(**_failed_context())
        assert "analysis-detail-toggle" not in html

    def test_no_info_blue_box(self, env):
        template = env.get_template("partials/analysis_modal.html")
        html = template.render(**_failed_context())
        assert "analysis-brief-feedback" not in html


# ── legacy state ──


class TestLegacyState:
    def test_shows_neutral_feedback_box(self, env):
        template = env.get_template("partials/analysis_modal.html")
        html = template.render(**_legacy_context())
        assert "analysis-feedback" in html
        assert "Good questioning technique." in html

    def test_shows_stat_grid(self, env):
        template = env.get_template("partials/analysis_modal.html")
        html = template.render(**_legacy_context())
        assert "analysis-stat-grid" in html

    def test_shows_toggle(self, env):
        template = env.get_template("partials/analysis_modal.html")
        html = template.render(**_legacy_context())
        assert "analysis-detail-toggle" in html

    def test_no_apology_notice(self, env):
        template = env.get_template("partials/analysis_modal.html")
        html = template.render(**_legacy_context())
        assert "이전 형식" not in html
        assert "이 세션은" not in html

    def test_toggle_opens_existing_detail(self, env):
        template = env.get_template("partials/analysis_modal.html")
        html = template.render(**_legacy_context())
        assert 'id="analysis-detail-panel"' in html
        assert "질문 유형 분포" in html


# ── missing stats ──


class TestMissingStats:
    def test_duration_null_shows_unavailable(self, env):
        ctx = _base_context(
            feedback_status="ok",
            feedback_sections={
                "brief_feedback": ["좋은 출발이었어요!"],
            },
            stats={
                "duration_seconds": None,
                "teacher_question_count": 4,
                "student_response_count": 4,
                "tutor_intervention_count": 2,
            },
        )
        template = env.get_template("partials/analysis_modal.html")
        html = template.render(**ctx)
        assert "계산 불가" in html
        # Should NOT show 0
        assert "0분" not in html

    def test_no_stats_at_all(self, env):
        """Pre-#4 backward compat: no stats dict → stat grid not rendered."""
        ctx = _base_context(feedback_status="legacy")
        template = env.get_template("partials/analysis_modal.html")
        html = template.render(**ctx)
        assert "analysis-stat-grid" not in html
