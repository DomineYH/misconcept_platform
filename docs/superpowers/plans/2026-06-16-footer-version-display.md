# Footer Dynamic Version Display Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Show the real, running app version in the page footer (e.g. `v0.4.1.0 (a1b2c3d · 2026-06-16)`), read from the `VERSION` file plus the live git commit, instead of the hardcoded stale `v0.1.0`.

**Architecture:** A new `src/version.py` module reads the hand-maintained `VERSION` file and queries the short git SHA + commit date once at import time (no git hook). The shared `Jinja2Templates` instance in `src/api/dependencies.py` exposes the assembled string as a global so every template's `layout.html` footer renders it. Git failures (e.g. zip deploy with no `.git`) degrade gracefully to base-version-only.

**Tech Stack:** Python 3.12, FastAPI, Jinja2, pytest. Code must pass `ruff` and `black` at line-length 80.

---

## Background / Current State

Four places hold a version today and they disagree:

| Location | Current value | Role |
|----------|---------------|------|
| `VERSION` (repo root) | `0.4.1.0` | **Source of truth** (matches `CHANGELOG.md`), hand-maintained |
| `src/templates/layout.html` footer | `v0.1.0` (hardcoded) | What users see — **stale, the bug** |
| `src/main.py` `FastAPI(version=...)` | `0.1.0` | OpenAPI docs — stale |
| `pyproject.toml` `version` | `0.1.0` | Package build metadata — **out of scope** (separate concern, leave as-is) |

This plan makes `VERSION` the single source for the displayed/runtime version and wires it into the footer dynamically. `pyproject.toml` is intentionally NOT touched.

**Format decision:** `v{base} ({short_sha} · {commit_date})`. Date is the short ISO commit date (`%cs` → `2026-06-16`). No `-dirty` flag (YAGNI). Middle dot is the literal `·` (U+00B7).

**Capture timing:** computed once at app startup via `git rev-parse` / `git show`. Reflects the commit the server is running. Restart picks up a new commit.

## File Structure

- **Create** `src/version.py` — version assembly. One responsibility: produce the display string. Pure formatter (`format_version`) split from I/O (`read_base_version`, `get_git_info`) so it is unit-testable without git.
- **Create** `tests/unit/test_version.py` — unit tests for the module.
- **Create** `tests/integration/test_footer_version.py` — end-to-end test that a rendered page shows the dynamic version.
- **Modify** `src/api/dependencies.py` — import `get_app_version`, set `templates.env.globals["app_version"]`.
- **Modify** `src/templates/layout.html` — footer uses `{{ app_version }}`.
- **Modify** `src/main.py` — `FastAPI(version=read_base_version())` (sync OpenAPI docs).
- **Modify** `CHANGELOG.md` — add `[Unreleased] → Added` entry.

---

## Task 1: Version module (`src/version.py`) with unit tests

**Files:**
- Create: `src/version.py`
- Test: `tests/unit/test_version.py`

- [ ] **Step 1: Write the failing unit tests**

Create `tests/unit/test_version.py`:

```python
"""Unit tests for the application version string builder."""

import src.version as version


class TestFormatVersion:
    """Pure formatting of the display version string."""

    def test_full_with_sha_and_date(self):
        result = version.format_version(
            "0.4.1.0", "a1b2c3d", "2026-06-16"
        )
        assert result == "v0.4.1.0 (a1b2c3d · 2026-06-16)"

    def test_sha_only_when_date_missing(self):
        result = version.format_version("0.4.1.0", "a1b2c3d", None)
        assert result == "v0.4.1.0 (a1b2c3d)"

    def test_base_only_when_git_unavailable(self):
        result = version.format_version("0.4.1.0", None, None)
        assert result == "v0.4.1.0"


class TestReadBaseVersion:
    """Reading the VERSION file."""

    def test_reads_and_strips_version_file(self, tmp_path, monkeypatch):
        vfile = tmp_path / "VERSION"
        vfile.write_text("9.9.9.9\n", encoding="utf-8")
        monkeypatch.setattr(version, "_VERSION_FILE", vfile)
        assert version.read_base_version() == "9.9.9.9"

    def test_returns_unknown_when_missing(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            version, "_VERSION_FILE", tmp_path / "nope"
        )
        assert version.read_base_version() == "unknown"


class TestGetAppVersion:
    """End-to-end assembly with git mocked out."""

    def test_falls_back_to_base_when_git_unavailable(self, monkeypatch):
        monkeypatch.setattr(
            version, "read_base_version", lambda: "0.4.1.0"
        )
        monkeypatch.setattr(
            version, "get_git_info", lambda: (None, None)
        )
        assert version.get_app_version() == "v0.4.1.0"

    def test_includes_git_info_when_available(self, monkeypatch):
        monkeypatch.setattr(
            version, "read_base_version", lambda: "0.4.1.0"
        )
        monkeypatch.setattr(
            version,
            "get_git_info",
            lambda: ("a1b2c3d", "2026-06-16"),
        )
        assert version.get_app_version() == (
            "v0.4.1.0 (a1b2c3d · 2026-06-16)"
        )
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `.venv/bin/pytest tests/unit/test_version.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'src.version'` (or `AttributeError`).

- [ ] **Step 3: Write `src/version.py`**

Create `src/version.py`:

```python
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
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `.venv/bin/pytest tests/unit/test_version.py -v`
Expected: PASS (7 tests).

- [ ] **Step 5: Lint the new file**

Run: `.venv/bin/ruff check src/version.py tests/unit/test_version.py && .venv/bin/black --check src/version.py tests/unit/test_version.py`
Expected: no errors. If black reports changes, run `.venv/bin/black src/version.py tests/unit/test_version.py` and re-run tests.

- [ ] **Step 6: Commit**

```bash
git add src/version.py tests/unit/test_version.py
git commit -m "feat: add app version string builder (VERSION + git)"
```

---

## Task 2: Wire version into the footer

**Files:**
- Modify: `src/api/dependencies.py` (import near line 15; global after line 18)
- Modify: `src/templates/layout.html` (footer block, currently shows `v0.1.0`)
- Test: `tests/integration/test_footer_version.py`

- [ ] **Step 1: Write the failing integration test**

Create `tests/integration/test_footer_version.py`:

```python
"""The rendered footer shows the dynamic app version, not v0.1.0."""

from fastapi.testclient import TestClient

from src.version import read_base_version


def test_login_footer_shows_dynamic_version(test_client: TestClient):
    response = test_client.get("/login")
    assert response.status_code == 200
    assert f"v{read_base_version()}" in response.text
    assert "v0.1.0" not in response.text
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `.venv/bin/pytest tests/integration/test_footer_version.py -v`
Expected: FAIL — footer still contains `v0.1.0`, so the `assert "v0.1.0" not in response.text` (and/or the base-version assert) fails.

- [ ] **Step 3: Add the version global in `src/api/dependencies.py`**

Add this import next to the existing `from src.db.connection import AsyncSessionLocal` (around line 15):

```python
from src.db.connection import AsyncSessionLocal
from src.version import get_app_version
```

Then, immediately after the existing line `templates = Jinja2Templates(directory="src/templates")` (line 18), add:

```python
# Shared Jinja2Templates instance
templates = Jinja2Templates(directory="src/templates")

# Expose the running app version to every template (footer, etc.).
# Computed once at import; reflects the commit the server is running.
templates.env.globals["app_version"] = get_app_version()
```

- [ ] **Step 4: Update the footer in `src/templates/layout.html`**

Find this block:

```html
  <footer>
    <p>
      오개념 교정 대화 시뮬레이터 v0.1.0 |
      교육 연구 도구
    </p>
  </footer>
```

Replace the hardcoded `v0.1.0` with the template variable:

```html
  <footer>
    <p>
      오개념 교정 대화 시뮬레이터 {{ app_version }} |
      교육 연구 도구
    </p>
  </footer>
```

- [ ] **Step 5: Run the integration test to verify it passes**

Run: `.venv/bin/pytest tests/integration/test_footer_version.py -v`
Expected: PASS — footer now renders `v0.4.1.0 (<sha> · <date>)` and no longer contains `v0.1.0`.

- [ ] **Step 6: Commit**

```bash
git add src/api/dependencies.py src/templates/layout.html tests/integration/test_footer_version.py
git commit -m "feat: render dynamic app version in footer"
```

---

## Task 3: Sync FastAPI OpenAPI version (bonus)

**Files:**
- Modify: `src/main.py` (import block; `FastAPI(...)` around lines 212-217)

- [ ] **Step 1: Add the import**

In the `from src...` import block of `src/main.py`, add next to `from src.config import config`:

```python
from src.config import config
from src.version import read_base_version
```

- [ ] **Step 2: Use the base version in the FastAPI app**

Find:

```python
app = FastAPI(
    title="Misconception Dialogue Simulator",
    description=("Three-party dialogue simulator for teacher training"),
    version="0.1.0",
    lifespan=lifespan,
)
```

Replace `version="0.1.0",` with:

```python
app = FastAPI(
    title="Misconception Dialogue Simulator",
    description=("Three-party dialogue simulator for teacher training"),
    version=read_base_version(),
    lifespan=lifespan,
)
```

- [ ] **Step 3: Verify the OpenAPI version reflects the VERSION file**

Run:

```bash
.venv/bin/python -c "from src.main import app; print(app.version)"
```

Expected: prints `0.4.1.0` (the current `VERSION` content), not `0.1.0`.

- [ ] **Step 4: Commit**

```bash
git add src/main.py
git commit -m "feat: sync FastAPI OpenAPI version with VERSION file"
```

---

## Task 4: Changelog entry

**Files:**
- Modify: `CHANGELOG.md` (under the `## [Unreleased]` heading)

- [ ] **Step 1: Add an Unreleased entry**

Find:

```markdown
## [Unreleased]

## [0.4.1.0] - 2026-04-28
```

Insert an `### Added` section under `## [Unreleased]`:

```markdown
## [Unreleased]

### Added
- 화면 푸터에 실행 중인 앱 버전 동적 표시 (`VERSION` 파일 + git 커밋
  해시·날짜). 기존 하드코딩된 `v0.1.0` 제거.
  - `src/version.py` 신규: `VERSION` 읽기 + `git rev-parse`/`git show`로
    짧은 커밋 해시·날짜 조회 (앱 시작 시 1회, git 없으면 버전만 표시)
  - `templates.env.globals["app_version"]`로 전역 주입 → 모든 페이지 푸터
  - FastAPI OpenAPI `version`도 `VERSION` 파일과 동기화

## [0.4.1.0] - 2026-04-28
```

- [ ] **Step 2: Commit**

```bash
git add CHANGELOG.md
git commit -m "docs: changelog for dynamic footer version"
```

---

## Task 5: Full verification + register GitHub issue

**Files:** none (verification + issue registration)

- [ ] **Step 1: Run the full test suite**

Run: `.venv/bin/pytest -q`
Expected: all tests pass (no regressions). If failures appear, fix before continuing — do NOT register the issue on a red suite.

- [ ] **Step 2: Lint the whole change set**

Run: `.venv/bin/ruff check src tests && .venv/bin/black --check src tests`
Expected: no errors.

- [ ] **Step 3: Manual smoke check of the rendered footer**

Run:

```bash
.venv/bin/python -c "from src.api.dependencies import templates; print(templates.env.globals['app_version'])"
```

Expected: prints something like `v0.4.1.0 (<7-char sha> · <YYYY-MM-DD>)`.

- [ ] **Step 4: Register the completed work as a GitHub issue**

Repo is `DomineYH/misconcept_platform`; `gh` is authenticated. Create the issue:

```bash
gh issue create \
  --title "feat: 푸터에 동적 앱 버전 표시 (VERSION + git 커밋)" \
  --body "$(cat <<'EOF'
## 구현 완료 (footer dynamic version)

화면 푸터가 하드코딩된 `v0.1.0` 대신 실제 실행 버전을 표시하도록 구현.

**표시 형식:** `v{VERSION} ({short_sha} · {commit_date})`
예) `v0.4.1.0 (a1b2c3d · 2026-06-16)`. git 없으면 `v0.4.1.0`만 표시.

### 변경 사항
- [x] `src/version.py` 신규 — `VERSION` 읽기 + git 커밋 해시·날짜 조회
      (앱 시작 시 1회, 실패 시 버전만으로 graceful fallback)
- [x] `src/api/dependencies.py` — `templates.env.globals["app_version"]`
      전역 주입 (모든 페이지 푸터에 자동 반영)
- [x] `src/templates/layout.html` — 푸터 `{{ app_version }}`로 교체
- [x] `src/main.py` — FastAPI OpenAPI `version`을 `VERSION` 파일과 동기화
- [x] 단위 테스트(`tests/unit/test_version.py`) + 통합 테스트
      (`tests/integration/test_footer_version.py`)
- [x] `CHANGELOG.md` `[Unreleased]` 항목 추가

### 범위 외 (의도적 제외)
- `pyproject.toml` 버전(빌드 메타데이터, 별개 개념)은 미연동
- git 훅 / 자동 버전 증가 / `-dirty` 플래그 (YAGNI)
EOF
)"
```

Expected: command prints the new issue URL. Record it.

- [ ] **Step 5: Report the issue URL to the user**

Paste the created issue URL into the final summary so the user can confirm the registration.

---

## Self-Review

- **Spec coverage:** display location (footer ✓ Task 2), source of truth (`VERSION` ✓ Tasks 1-3), capture timing (startup git query ✓ Task 1), graceful git-absent fallback (✓ Task 1 tests), format `v{base} (sha · date)` (✓ Task 1), bonus main.py sync (✓ Task 3), CHANGELOG (✓ Task 4), register issue after implementation (✓ Task 5). No gaps.
- **Placeholders:** none — all code and commands are concrete.
- **Type consistency:** `read_base_version`, `get_git_info`, `format_version`, `get_app_version` names are used identically across Tasks 1-3 and the tests. `get_app_version` (full string) feeds the template global; `read_base_version` (bare `0.4.1.0`) feeds FastAPI.
- **Note:** `.venv/bin/pytest` assumes the project venv. If the runner uses `uv`, substitute `uv run pytest` etc.
