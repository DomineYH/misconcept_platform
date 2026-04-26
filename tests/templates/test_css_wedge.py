"""Static asset tests: wedge CSS breakpoint media queries."""

import re

CSS_PATH = "static/css/styles.css"


def _read_css():
    with open(CSS_PATH, encoding="utf-8") as f:
        return f.read()


class TestCSSWedgeBreakpoints:
    """Issue #28 wedge section must have responsive breakpoints."""

    def test_has_issue_28_banner(self):
        css = _read_css()
        assert "Issue #28" in css

    def test_has_small_breakpoint_under_480(self):
        css = _read_css()
        pat = r"@media\s*\(\s*max-width\s*:\s*479px\s*\)"
        assert re.search(pat, css) is not None

    def test_has_medium_breakpoint_480_767(self):
        css = _read_css()
        pat = (
            r"@media\s*\(\s*min-width\s*:\s*480px\s*\)"
            r"\s*and\s*"
            r"\(\s*max-width\s*:\s*767px\s*\)"
        )
        assert re.search(pat, css) is not None

    def test_wedge_uses_info_blue_tokens(self):
        css = _read_css()
        assert "var(--color-info-bg)" in css
        assert "var(--color-info-text)" in css
        assert "var(--color-mentor-border)" in css

    def test_no_purple_hex_in_wedge(self):
        css = _read_css()
        banner = css.find("Issue #28")
        assert banner != -1, "Issue #28 banner not found"
        after_banner = css[banner:]
        next_section = after_banner.find("\n/* ===", 10)
        if next_section != -1:
            wedge_css = after_banner[:next_section]
        else:
            wedge_css = after_banner[:2000]
        purples = [
            "#9C27B0",
            "#7B1FA2",
            "#CE93D8",
            "#BA68C8",
            "#AB47BC",
            "#8E24AA",
            "#6A1B9A",
            "#4A148C",
        ]
        for purple in purples:
            assert (
                purple.lower() not in wedge_css.lower()
            ), f"Purple hex {purple} in wedge CSS"

    def test_stat_grid_uses_css_grid(self):
        css = _read_css()
        assert "display: grid" in css
        assert "grid-template-columns" in css
