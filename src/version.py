"""Application version string for display in the UI footer.

The base version is maintained by hand in the repo-root ``VERSION``
file. The short git commit hash and commit date are read once at import
time so the footer reflects exactly which commit is running. When git is
unavailable (e.g. a zip deploy without a ``.git`` directory) only the
base version is shown.
"""

import subprocess
from pathlib import Path

# src/version.py -> parent (src/) -> parent (repo root) -> VERSION
_VERSION_FILE = Path(__file__).resolve().parent.parent / "VERSION"


def read_base_version() -> str:
    """Return the version from the VERSION file, or 'unknown'."""
    try:
        return _VERSION_FILE.read_text(encoding="utf-8").strip()
    except OSError:
        return "unknown"


def _run_git(args: list[str]) -> str | None:
    """Run a git command; return stripped stdout or None on failure."""
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=_VERSION_FILE.parent,
            capture_output=True,
            text=True,
            timeout=2,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode != 0:
        return None
    return result.stdout.strip() or None


def get_git_info() -> tuple[str | None, str | None]:
    """Return (short_sha, commit_date) or (None, None) if unavailable."""
    sha = _run_git(["rev-parse", "--short", "HEAD"])
    date = _run_git(["show", "-s", "--format=%cs", "HEAD"])
    return sha, date


def format_version(base: str, sha: str | None, date: str | None) -> str:
    """Format the display string from its parts (pure function).

    Examples::

        format_version("0.4.1.0", "a1b2c3d", "2026-06-16")
            -> "v0.4.1.0 (a1b2c3d · 2026-06-16)"
        format_version("0.4.1.0", "a1b2c3d", None)
            -> "v0.4.1.0 (a1b2c3d)"
        format_version("0.4.1.0", None, None)
            -> "v0.4.1.0"
    """
    label = f"v{base}"
    if sha and date:
        return f"{label} ({sha} · {date})"
    if sha:
        return f"{label} ({sha})"
    return label


def get_app_version() -> str:
    """Return the full version string for display."""
    base = read_base_version()
    sha, date = get_git_info()
    return format_version(base, sha, date)
