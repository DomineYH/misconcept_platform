"""Contract tests for message color tokens (Issue #15).

Guards the student/mentor/tutor role token system in static/css/styles.css.
These tests are intentionally structural: they parse the CSS as text and
verify that:

1. The role tokens are declared in both light (:root) and dark
   (@media (prefers-color-scheme: dark) :root) scopes.
2. The bubble rules reference the tokens rather than hardcoded hex values.
3. The previously-present hardcoded mentor hex (#f3f4f6/#111827/#6b7280)
   is gone — critical regression guard for the dark-mode leak bug.
4. The redundant dark-mode override for .message-student is removed.
5. WCAG AA contrast ratios are met for all mentor foreground/background
   combinations in both light and dark.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

STYLES_CSS = Path(__file__).resolve().parents[2] / "static" / "css" / "styles.css"

LIGHT_TOKENS = {
    "--color-student-bg": "#FFFFFF",
    "--color-student-border": "#EEEEEE",
    "--color-student-text": "#000000",
    "--color-mentor-bg": "#E3F2FD",
    "--color-mentor-border": "#1565C0",
    "--color-mentor-text": "#0D47A1",
}

DARK_TOKENS = {
    "--color-student-bg": "#121212",
    "--color-student-border": "#2A2A2A",
    "--color-student-text": "#FFFFFF",
    "--color-mentor-bg": "#1A2A3D",
    "--color-mentor-border": "#64B5F6",
    "--color-mentor-text": "#BBDEFB",
}


@pytest.fixture(scope="module")
def css_source() -> str:
    assert STYLES_CSS.is_file(), f"styles.css not found at {STYLES_CSS}"
    return STYLES_CSS.read_text(encoding="utf-8")


def _extract_light_root(css: str) -> str:
    """Extract the top-level :root { ... } block (light mode)."""
    match = re.search(r"^:root\s*\{([^}]*)\}", css, flags=re.MULTILINE | re.DOTALL)
    assert match, "Top-level :root block not found"
    return match.group(1)


def _extract_dark_root(css: str) -> str:
    """Extract the :root block inside @media (prefers-color-scheme: dark)."""
    match = re.search(
        r"@media\s*\(prefers-color-scheme:\s*dark\)\s*\{\s*:root\s*\{([^}]*)\}",
        css,
        flags=re.DOTALL,
    )
    assert match, "Dark-mode :root block not found"
    return match.group(1)


def _extract_rule(css: str, selector: str) -> str:
    """Extract the first rule body for `selector` (order-sensitive)."""
    pattern = re.escape(selector) + r"\s*\{([^}]*)\}"
    match = re.search(pattern, css)
    assert match, f"Rule {selector!r} not found"
    return match.group(1)


def _assert_token(block: str, name: str, expected: str) -> None:
    pattern = re.escape(name) + r"\s*:\s*([^;]+);"
    match = re.search(pattern, block)
    assert match, f"Token {name} missing from block"
    actual = match.group(1).strip().upper()
    assert actual == expected.upper(), (
        f"Token {name} expected {expected!r}, got {actual!r}"
    )


def _relative_luminance(hex_color: str) -> float:
    h = hex_color.lstrip("#")
    r, g, b = (int(h[i : i + 2], 16) / 255.0 for i in (0, 2, 4))

    def chan(c: float) -> float:
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

    rl, gl, bl = chan(r), chan(g), chan(b)
    return 0.2126 * rl + 0.7152 * gl + 0.0722 * bl


def _contrast_ratio(fg: str, bg: str) -> float:
    l1, l2 = _relative_luminance(fg), _relative_luminance(bg)
    lighter, darker = max(l1, l2), min(l1, l2)
    return (lighter + 0.05) / (darker + 0.05)


def test_mentor_tokens_defined_in_light_mode(css_source: str) -> None:
    """Mentor triplet must exist in :root with exact values."""
    root = _extract_light_root(css_source)
    for name in ("--color-mentor-bg", "--color-mentor-border", "--color-mentor-text"):
        _assert_token(root, name, LIGHT_TOKENS[name])


def test_mentor_tokens_defined_in_dark_mode(css_source: str) -> None:
    """Mentor triplet must also be defined in @media dark :root."""
    root = _extract_dark_root(css_source)
    for name in ("--color-mentor-bg", "--color-mentor-border", "--color-mentor-text"):
        _assert_token(root, name, DARK_TOKENS[name])


def test_student_tokens_defined_both_modes(css_source: str) -> None:
    """Student triplet must exist in both :root and dark :root."""
    light = _extract_light_root(css_source)
    dark = _extract_dark_root(css_source)
    for name in ("--color-student-bg", "--color-student-border", "--color-student-text"):
        _assert_token(light, name, LIGHT_TOKENS[name])
        _assert_token(dark, name, DARK_TOKENS[name])


def test_mentor_bubble_no_hardcoded_hex(css_source: str) -> None:
    """REGRESSION GUARD: the old mentor hex values must not appear in the
    .message-mentor .message-bubble rule. These were the source of the
    dark-mode leak before token-ification."""
    body = _extract_rule(css_source, ".message-mentor .message-bubble")
    forbidden = ("#f3f4f6", "#111827", "#6b7280")
    for hex_value in forbidden:
        assert hex_value.lower() not in body.lower(), (
            f"Forbidden hex {hex_value} found in .message-mentor .message-bubble"
        )


def test_mentor_bubble_uses_role_tokens(css_source: str) -> None:
    """.message-mentor .message-bubble must reference the mentor tokens."""
    body = _extract_rule(css_source, ".message-mentor .message-bubble")
    assert "var(--color-mentor-bg)" in body
    assert "var(--color-mentor-border)" in body


def test_student_bubble_uses_role_tokens(css_source: str) -> None:
    body = _extract_rule(css_source, ".message-student .message-bubble")
    assert "var(--color-student-bg)" in body
    assert "var(--color-student-text)" in body
    assert "var(--color-student-border)" in body


def test_tutor_bubble_uses_role_tokens(css_source: str) -> None:
    """Tutor bubble parity fix — was using --color-gray-100 before."""
    body = _extract_rule(css_source, ".message-tutor .message-bubble")
    assert "var(--color-tutor-bg)" in body
    assert "var(--color-tutor-text)" in body
    assert "var(--color-tutor-border)" in body


def test_mentor_sender_rule_exists(css_source: str) -> None:
    """New rule .message-mentor .message-sender must set mentor-text color."""
    body = _extract_rule(css_source, ".message-mentor .message-sender")
    assert "var(--color-mentor-text)" in body


def _extract_dark_media_block(css: str) -> str:
    """Return the full body of the `@media (prefers-color-scheme: dark)`
    block via balanced-brace counting. Python's re module cannot match
    balanced braces, and a naive lazy `.*?\\n}` would stop at the first
    nested `}` (typically the end of the inner `:root {}`), giving a
    false-negative window for regressions inside the @media scope.
    """
    opener_re = re.compile(r"@media\s*\(prefers-color-scheme:\s*dark\)\s*\{")
    opener = opener_re.search(css)
    assert opener, "Dark @media block opener not found"
    start = opener.end()
    depth = 1
    i = start
    while i < len(css) and depth > 0:
        ch = css[i]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return css[start:i]
        i += 1
    raise AssertionError("Dark @media block never closed")


def test_redundant_dark_student_override_removed(css_source: str) -> None:
    """The .message-student .message-bubble override anywhere inside the
    dark @media block is gone — its values now match the new tokens
    exactly. Uses balanced-brace extraction so any re-introduction after
    the nested :root {} is still detected."""
    dark_block = _extract_dark_media_block(css_source)
    assert ".message-student .message-bubble" not in dark_block, (
        "Redundant dark-mode override for .message-student still present"
    )


@pytest.mark.parametrize(
    "mode,fg,bg,label",
    [
        ("light mentor body", "#000000", LIGHT_TOKENS["--color-mentor-bg"], "body"),
        ("light mentor label", LIGHT_TOKENS["--color-mentor-text"], LIGHT_TOKENS["--color-mentor-bg"], "label"),
        ("dark mentor body", "#FFFFFF", DARK_TOKENS["--color-mentor-bg"], "body"),
        ("dark mentor label", DARK_TOKENS["--color-mentor-text"], DARK_TOKENS["--color-mentor-bg"], "label"),
    ],
)
def test_wcag_aa_contrast_ratios(mode: str, fg: str, bg: str, label: str) -> None:
    """WCAG AA requires ≥ 4.5:1 for normal text. All four mentor combinations
    exceed AA per the issue-15 contrast table."""
    ratio = _contrast_ratio(fg, bg)
    assert ratio >= 4.5, f"{mode}: contrast {ratio:.2f}:1 < 4.5:1 (WCAG AA)"
