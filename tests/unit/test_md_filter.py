"""Unit tests for markdown-to-HTML Jinja2 filter."""

from markupsafe import Markup


def get_md_filter():
    """Import the md filter function."""
    from src.api.dependencies import md_filter

    return md_filter


class TestMdFilter:
    """Test markdown conversion filter."""

    def test_bold_text(self):
        md = get_md_filter()
        result = md("이것은 **굵은 글씨**입니다")
        assert "<strong>굵은 글씨</strong>" in result

    def test_italic_text(self):
        md = get_md_filter()
        result = md("이것은 *기울임*입니다")
        assert "<em>기울임</em>" in result

    def test_returns_markup(self):
        md = get_md_filter()
        result = md("**test**")
        assert isinstance(result, Markup)

    def test_empty_string(self):
        md = get_md_filter()
        result = md("")
        assert result == Markup("")

    def test_none_input(self):
        md = get_md_filter()
        result = md(None)
        assert result == Markup("")

    def test_plain_text_no_change(self):
        md = get_md_filter()
        result = md("일반 텍스트")
        assert "일반 텍스트" in result

    def test_xss_prevention(self):
        md = get_md_filter()
        result = md("<script>alert('xss')</script>")
        assert "<script>" not in result
        assert "&lt;script&gt;" in result

    def test_newline_to_br(self):
        md = get_md_filter()
        result = md("첫째 줄\n둘째 줄")
        assert "<br" in result

    def test_bullet_list(self):
        md = get_md_filter()
        result = md("- 항목1\n- 항목2")
        assert "<li>" in result

    def test_numbered_list(self):
        md = get_md_filter()
        result = md("1. 첫째\n2. 둘째")
        assert "<li>" in result

    def test_mixed_markdown(self):
        md = get_md_filter()
        text = "**제목**: 이것은 *중요한* 내용입니다"
        result = md(text)
        assert "<strong>제목</strong>" in result
        assert "<em>중요한</em>" in result

    def test_filter_registered_on_templates(self):
        from src.api.dependencies import templates

        assert "md" in templates.env.filters
