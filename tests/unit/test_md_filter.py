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


class TestMdFilterXssSanitization:
    """Regression tests for URL scheme XSS neutralization in md_filter."""

    def test_javascript_href_neutralized(self):
        """javascript: href must NOT appear in output."""
        md = get_md_filter()
        result = str(md("[x](javascript:alert(1))"))
        assert "javascript:" not in result

    def test_javascript_src_neutralized(self):
        """javascript: src in img must NOT appear in output."""
        md = get_md_filter()
        result = str(md("![x](javascript:alert(2))"))
        assert "javascript:" not in result

    def test_data_url_href_neutralized(self):
        """data: href must NOT appear in output."""
        md = get_md_filter()
        result = str(md("[x](data:text/html,<h1>xss</h1>)"))
        assert "data:" not in result

    def test_vbscript_href_neutralized(self):
        """vbscript: href must NOT appear in output."""
        md = get_md_filter()
        result = str(md("[x](vbscript:evil())"))
        assert "vbscript:" not in result

    def test_safe_https_link_preserved(self):
        """https:// links must pass through unchanged."""
        md = get_md_filter()
        result = str(md("[link](https://example.com)"))
        assert 'href="https://example.com"' in result

    def test_safe_http_link_preserved(self):
        """http:// links must pass through unchanged."""
        md = get_md_filter()
        result = str(md("[link](http://example.com)"))
        assert 'href="http://example.com"' in result

    def test_mailto_link_preserved(self):
        """mailto: links must pass through unchanged."""
        md = get_md_filter()
        result = str(md("[email](mailto:foo@bar.com)"))
        assert 'href="mailto:foo@bar.com"' in result

    def test_relative_link_preserved(self):
        """Relative path links must pass through unchanged."""
        md = get_md_filter()
        result = str(md("[rel](/some/path)"))
        assert 'href="/some/path"' in result

    def test_anchor_link_preserved(self):
        """# anchor links must pass through unchanged."""
        md = get_md_filter()
        result = str(md("[anchor](#section)"))
        assert 'href="#section"' in result

    def test_existing_behavior_unaffected(self):
        """Bold, italic, nl2br and raw-HTML escaping still work."""
        md = get_md_filter()
        bold = str(md("**bold**"))
        assert "<strong>bold</strong>" in bold

        italic = str(md("*italic*"))
        assert "<em>italic</em>" in italic

        br = str(md("line1\nline2"))
        assert "<br" in br

        xss_raw = str(md("<script>alert('xss')</script>"))
        assert "<script>" not in xss_raw
        assert "&lt;script&gt;" in xss_raw
