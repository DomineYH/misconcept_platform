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


def _extract_all_rules(css: str, selector: str) -> list[str]:
    """Return every rule body for `selector` across the whole stylesheet
    in source order. Callers should assert their invariants against ALL
    occurrences so a later override introduced higher in the cascade
    cannot produce a false-green test.
    """
    pattern = re.escape(selector) + r"\s*\{([^}]*)\}"
    matches = [m.group(1) for m in re.finditer(pattern, css)]
    assert matches, f"Rule {selector!r} not found"
    return matches


def _extract_token_from_light_root(css: str, token: str) -> str:
    """Return the value of `token` declared in the top-level :root block."""
    root = _extract_light_root(css)
    match = re.search(re.escape(token) + r"\s*:\s*([^;]+);", root)
    assert match, f"Token {token} not found in light :root"
    return match.group(1).strip().upper()


def _extract_token_from_dark_root(css: str, token: str) -> str:
    """Return the value of `token` declared in the dark-mode :root block."""
    root = _extract_dark_root(css)
    match = re.search(re.escape(token) + r"\s*:\s*([^;]+);", root)
    assert match, f"Token {token} not found in dark :root"
    return match.group(1).strip().upper()


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
    """REGRESSION GUARD: the old mentor hex values must not appear in
    ANY .message-mentor .message-bubble rule, including later cascade
    overrides. Iterating all occurrences so a re-added hex elsewhere in
    the sheet cannot produce a false-green test."""
    bodies = _extract_all_rules(css_source, ".message-mentor .message-bubble")
    forbidden = ("#f3f4f6", "#111827", "#6b7280")
    for i, body in enumerate(bodies):
        for hex_value in forbidden:
            assert hex_value.lower() not in body.lower(), (
                f"Forbidden hex {hex_value} found in occurrence #{i} of "
                f".message-mentor .message-bubble"
            )


def test_mentor_bubble_uses_role_tokens(css_source: str) -> None:
    """.message-mentor .message-bubble must reference the mentor tokens.
    The primary (first) occurrence must wire bg and border to tokens."""
    bodies = _extract_all_rules(css_source, ".message-mentor .message-bubble")
    body = bodies[0]
    assert "var(--color-mentor-bg)" in body
    assert "var(--color-mentor-border)" in body


def test_student_bubble_uses_role_tokens(css_source: str) -> None:
    bodies = _extract_all_rules(css_source, ".message-student .message-bubble")
    body = bodies[0]
    assert "var(--color-student-bg)" in body
    assert "var(--color-student-text)" in body
    assert "var(--color-student-border)" in body


def test_tutor_bubble_uses_role_tokens(css_source: str) -> None:
    """Tutor bubble parity fix — was using --color-gray-100 before."""
    bodies = _extract_all_rules(css_source, ".message-tutor .message-bubble")
    body = bodies[0]
    assert "var(--color-tutor-bg)" in body
    assert "var(--color-tutor-text)" in body
    assert "var(--color-tutor-border)" in body


def test_mentor_sender_rule_exists(css_source: str) -> None:
    """New rule .message-mentor .message-sender must set mentor-text color."""
    bodies = _extract_all_rules(css_source, ".message-mentor .message-sender")
    body = bodies[0]
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
    dark @media block is gone. Uses a selector-shape regex so that any
    re-introduction — including higher-specificity rewrites like
    `.message.message-student .message-bubble` or
    `.messages-container .message-student .message-bubble` — is also
    detected. The earlier literal-substring check only caught the exact
    two-class form.
    """
    dark_block = _extract_dark_media_block(css_source)
    override_pattern = re.compile(
        r"\.message-student\b[^{}]*\.message-bubble\s*\{"
    )
    match = override_pattern.search(dark_block)
    assert match is None, (
        "Redundant dark-mode override for .message-student still present: "
        f"matched {match.group(0) if match else ''!r}"
    )


def _mentor_contrast_cases(css: str) -> list[tuple[str, str, str]]:
    """Build the four WCAG check cases from the *actual* tokens in CSS
    rather than hardcoded hexes. If `--color-text-primary` drifts in
    either mode, the contrast test follows the drift and can flag a
    real regression.

    Rendered pairs guarded:
      light body  : .message-mentor .message-bubble color
                   (= --color-text-primary, light) on --color-mentor-bg
      light label : .message-mentor .message-sender color
                   (= --color-mentor-text) on --color-mentor-bg
      dark body   : --color-text-primary, dark on --color-mentor-bg dark
      dark label  : --color-mentor-text dark on --color-mentor-bg dark
    """
    light_bg = _extract_token_from_light_root(css, "--color-mentor-bg")
    light_label_fg = _extract_token_from_light_root(css, "--color-mentor-text")
    light_body_fg = _extract_token_from_light_root(css, "--color-text-primary")
    dark_bg = _extract_token_from_dark_root(css, "--color-mentor-bg")
    dark_label_fg = _extract_token_from_dark_root(css, "--color-mentor-text")
    dark_body_fg = _extract_token_from_dark_root(css, "--color-text-primary")
    return [
        ("light mentor body", light_body_fg, light_bg),
        ("light mentor label", light_label_fg, light_bg),
        ("dark mentor body", dark_body_fg, dark_bg),
        ("dark mentor label", dark_label_fg, dark_bg),
    ]


def test_wcag_aa_contrast_ratios(css_source: str) -> None:
    """WCAG AA requires ≥ 4.5:1 for normal text. All four rendered mentor
    combinations (derived from the CSS itself, not hardcoded hexes) must
    clear AA. If a token value drifts in the future, this catches the
    resulting contrast regression."""
    for mode, fg, bg in _mentor_contrast_cases(css_source):
        ratio = _contrast_ratio(fg, bg)
        assert ratio >= 4.5, f"{mode}: contrast {ratio:.2f}:1 (fg {fg} / bg {bg}) < 4.5:1 (WCAG AA)"
