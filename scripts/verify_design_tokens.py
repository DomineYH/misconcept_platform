"""Verify every CSS token declared in styles.css is documented in DESIGN.md.

Run from the repo root:

    python scripts/verify_design_tokens.py

Exit code 0 when every ``--token-name`` declared in ``static/css/styles.css``
(under ``:root`` or the dark-mode ``@media`` override) appears as a literal
string in ``DESIGN.md``. Non-zero when any token is missing — the list of
missing tokens is printed to stderr.

Wired as a local pre-commit hook in ``.pre-commit-config.yaml`` so token
drift is caught at commit time.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CSS_PATH = REPO_ROOT / "static" / "css" / "styles.css"
DOC_PATH = REPO_ROOT / "DESIGN.md"

TOKEN_RE = re.compile(r"(--[a-z0-9-]+)\s*:", re.IGNORECASE)


def extract_tokens(css_text: str) -> list[str]:
    return sorted(set(TOKEN_RE.findall(css_text)))


def main() -> int:
    if not CSS_PATH.exists():
        print(f"ERROR: {CSS_PATH} not found", file=sys.stderr)
        return 2
    if not DOC_PATH.exists():
        print(f"ERROR: {DOC_PATH} not found", file=sys.stderr)
        return 2

    css_text = CSS_PATH.read_text(encoding="utf-8")
    doc_text = DOC_PATH.read_text(encoding="utf-8")

    tokens = extract_tokens(css_text)
    missing = [t for t in tokens if t not in doc_text]

    for token in tokens:
        mark = "FAIL" if token in missing else "PASS"
        print(f"{mark} {token}")

    if missing:
        print(
            f"\n{len(missing)} token(s) missing from DESIGN.md:",
            file=sys.stderr,
        )
        for token in missing:
            print(f"  - {token}", file=sys.stderr)
        print(
            "\nAdd the missing token(s) to DESIGN.md "
            "(literal string, e.g., `--color-foo`).",
            file=sys.stderr,
        )
        return 1

    print(f"\nAll {len(tokens)} token(s) documented in DESIGN.md.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
