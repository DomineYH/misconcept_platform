"""Contract tests for issue #24: unified session button markup.

Validates that chat.html serves the unified "대화 종료 후 분석 보기" button
and no longer includes a separate #analyze-btn in the header.
"""

from pathlib import Path

TEMPLATE = (
    Path(__file__).resolve().parents[2] / "src" / "templates" / "chat.html"
)


def _read_template() -> str:
    return TEMPLATE.read_text(encoding="utf-8")


def test_analyze_btn_removed_from_header():
    html = _read_template()
    assert (
        "analyze-btn" not in html
    ), "#analyze-btn must be removed — use the unified #end-session-btn flow"


def test_end_session_btn_present_as_primary():
    html = _read_template()
    assert 'id="end-session-btn"' in html
    assert 'class="btn-primary"' in html  # unified button is primary now
    # State machine marker
    assert "data-state=" in html


def test_unified_button_label():
    html = _read_template()
    assert "대화 종료 후 분석 보기" in html


def test_guidance_text_updated():
    html = _read_template()
    # Old guidance must not reference the two-button flow
    assert "대화 종료를 클릭한 후" not in html
    assert "분석하기를 클릭해 보세요" not in html
    # New guidance references the unified label
    assert "대화 종료 후 분석 보기" in html


def test_return_to_scenarios_btn_preserved():
    html = _read_template()
    assert 'id="return-to-scenarios-btn"' in html
