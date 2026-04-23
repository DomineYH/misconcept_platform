"""Verify every CSS token declared in styles.css is documented in DESIGN.md.

Separately validates light-mode tokens (declared in top-level ``:root``)
and dark-mode tokens (declared under ``@media (prefers-color-scheme: dark)``).

- Every token declared in either CSS block must appear somewhere in
  ``DESIGN.md``.
- Every token declared in the dark-mode block must additionally appear
  inside a ``Dark:`` labelled section of ``DESIGN.md`` (a section that
  starts at a ``Dark:`` label line and ends at the next ``Light:`` /
  ``Dark:`` label or markdown heading).

This catches a class of drift the earlier version of the script missed:
adding a dark-mode override for a token in CSS without documenting the
dark value in ``DESIGN.md``.

Wired as a local pre-commit hook in ``.pre-commit-config.yaml``.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CSS_PATH = REPO_ROOT / "static" / "css" / "styles.css"
DOC_PATH = REPO_ROOT / "DESIGN.md"

CSS_TOKEN_RE = re.compile(r"(--[a-z0-9-]+)\s*:", re.IGNORECASE)
DOC_TOKEN_RE = re.compile(r"--[a-z][a-z0-9-]*", re.IGNORECASE)
DARK_MEDIA_RE = re.compile(
    r"@media\s*\(\s*prefers-color-scheme\s*:\s*dark\s*\)"
)

DOC_LIGHT_LABEL_RE = re.compile(r"(?im)^Light\s*:\s*$")
DOC_DARK_LABEL_RE = re.compile(r"(?im)^Dark(?:\s*\(overrides\))?\s*:\s*$")
DOC_HEADING_RE = re.compile(r"(?m)^#{1,6}\s")


def split_css(css_text: str) -> tuple[set[str], set[str]]:
    match = DARK_MEDIA_RE.search(css_text)
    if match is None:
        return set(CSS_TOKEN_RE.findall(css_text)), set()
    light_part = css_text[: match.start()]
    dark_part = css_text[match.start() :]
    return (
        set(CSS_TOKEN_RE.findall(light_part)),
        set(CSS_TOKEN_RE.findall(dark_part)),
    )


def collect_section(doc_text: str, label_re: re.Pattern[str]) -> set[str]:
    """Return tokens that appear under any label matching ``label_re``."""
    documented: set[str] = set()
    for match in label_re.finditer(doc_text):
        start = match.end()
        ends = []
        for other_re in (
            DOC_LIGHT_LABEL_RE,
            DOC_DARK_LABEL_RE,
            DOC_HEADING_RE,
        ):
            nxt = other_re.search(doc_text, start)
            if nxt is not None:
                ends.append(nxt.start())
        end = min(ends) if ends else len(doc_text)
        block = doc_text[start:end]
        documented.update(DOC_TOKEN_RE.findall(block))
    return documented


def main() -> int:
    if not CSS_PATH.exists():
        print(f"ERROR: {CSS_PATH} not found", file=sys.stderr)
        return 2
    if not DOC_PATH.exists():
        print(f"ERROR: {DOC_PATH} not found", file=sys.stderr)
        return 2

    css_text = CSS_PATH.read_text(encoding="utf-8")
    doc_text = DOC_PATH.read_text(encoding="utf-8")

    css_light, css_dark = split_css(css_text)
    doc_any = set(DOC_TOKEN_RE.findall(doc_text))
    doc_dark = collect_section(doc_text, DOC_DARK_LABEL_RE)

    missing_light = sorted(css_light - doc_any)
    missing_dark = sorted(css_dark - doc_dark)

    print("Light :root tokens:")
    for token in sorted(css_light):
        mark = "FAIL" if token in missing_light else "PASS"
        print(f"  {mark} {token}")

    print("\nDark-mode override tokens:")
    if css_dark:
        for token in sorted(css_dark):
            mark = "FAIL" if token in missing_dark else "PASS"
            print(f"  {mark} {token}")
    else:
        print("  (no @media (prefers-color-scheme: dark) block found)")

    total_missing = len(missing_light) + len(missing_dark)

    if total_missing:
        print(
            f"\n{total_missing} token(s) missing from DESIGN.md:",
            file=sys.stderr,
        )
        if missing_light:
            print(
                "\n  Missing from DESIGN.md (any section):",
                file=sys.stderr,
            )
            for token in missing_light:
                print(f"    - {token}", file=sys.stderr)
        if missing_dark:
            print(
                "\n  Missing from a 'Dark:' labelled section " "of DESIGN.md:",
                file=sys.stderr,
            )
            for token in missing_dark:
                print(f"    - {token}", file=sys.stderr)
        print(
            "\nAdd the missing token(s) under the matching theme label "
            "('Light:' / 'Dark:') in DESIGN.md.",
            file=sys.stderr,
        )
        return 1

    print(
        f"\nAll {len(css_light)} light token(s) documented. "
        f"All {len(css_dark)} dark override token(s) documented under "
        f"a 'Dark:' section."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
