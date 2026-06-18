"""Unit tests for the application version string builder."""

import src.version as version


class TestFormatVersion:
    """Pure formatting of the display version string."""

    def test_full_with_sha_and_date(self):
        result = version.format_version("0.4.1.0", "a1b2c3d", "2026-06-16")
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
        monkeypatch.setattr(version, "_VERSION_FILE", tmp_path / "nope")
        assert version.read_base_version() == "unknown"


class TestRunGit:
    """The git subprocess wrapper degrades gracefully."""

    def test_run_git_returns_none_on_non_repo(self, monkeypatch, tmp_path):
        # tmp_path is not a git repo, so git exits non-zero ->
        # _run_git must return None (never raise).
        # Clear inherited git env (set when pytest runs inside a git hook),
        # otherwise git resolves the real repo via $GIT_DIR regardless of cwd.
        monkeypatch.delenv("GIT_DIR", raising=False)
        monkeypatch.delenv("GIT_INDEX_FILE", raising=False)
        monkeypatch.setattr(version, "_VERSION_FILE", tmp_path / "VERSION")
        assert version._run_git(["rev-parse", "--short", "HEAD"]) is None


class TestGetAppVersion:
    """End-to-end assembly with git mocked out."""

    def test_falls_back_to_base_when_git_unavailable(self, monkeypatch):
        monkeypatch.setattr(version, "read_base_version", lambda: "0.4.1.0")
        monkeypatch.setattr(version, "get_git_info", lambda: (None, None))
        assert version.get_app_version() == "v0.4.1.0"

    def test_includes_git_info_when_available(self, monkeypatch):
        monkeypatch.setattr(version, "read_base_version", lambda: "0.4.1.0")
        monkeypatch.setattr(
            version,
            "get_git_info",
            lambda: ("a1b2c3d", "2026-06-16"),
        )
        assert version.get_app_version() == ("v0.4.1.0 (a1b2c3d · 2026-06-16)")
