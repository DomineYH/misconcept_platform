"""Tests for prompt template hash and token count (E9)."""

from pathlib import Path

from src.services.session_synthesizer import prompt_hash
from src.utils.cache import load_prompt_template

PROMPT_PATH = (
    Path(__file__).resolve().parents[2]
    / "src"
    / "prompts"
    / "session_synthesis_prompt.txt"
)


class TestPromptTemplate:
    """Tests for session_synthesis_prompt.txt."""

    def test_template_exists(self):
        """Prompt template file exists."""
        assert PROMPT_PATH.exists()

    def test_template_loads(self):
        """Prompt template loads via cache utility."""
        content = load_prompt_template("session_synthesis_prompt.txt")
        assert len(content) > 0

    def test_stable_prefix_min_tokens(self):
        """Framework + instructions prefix ≥ 1024 tokens.

        Uses heuristic: len(text.split()) * 1.3 ≥ 1024.
        The prefix is everything before the scenario section.
        """
        content = load_prompt_template("session_synthesis_prompt.txt")
        # Find the scenario section — that's where volatile
        # content begins
        scenario_marker = "## Scenario"
        prefix = content.split(scenario_marker)[0]

        # Heuristic: word_count * 1.3 ≈ token count
        word_count = len(prefix.split())
        estimated_tokens = word_count * 1.3

        assert estimated_tokens >= 1024, (
            f"Prompt prefix estimated at {estimated_tokens:.0f} "
            f"tokens (need ≥1024 for OpenAI prompt caching). "
            f"Word count: {word_count}"
        )

    def test_template_has_required_placeholders(self):
        """Template contains all required format placeholders."""
        content = load_prompt_template("session_synthesis_prompt.txt")
        required = [
            "{framework_name}",
            "{framework_labels_with_criteria}",
            "{framework_labels}",
            "{scenario_title}",
            "{misconception}",
            "{student_profile}",
            "{dialogue_transcript}",
        ]
        for placeholder in required:
            assert placeholder in content, f"Missing placeholder: {placeholder}"

    def test_template_hash_stable(self):
        """Same template content produces same hash."""
        content = load_prompt_template("session_synthesis_prompt.txt")
        h1 = prompt_hash(content)
        h2 = prompt_hash(content)
        assert h1 == h2

    def test_hash_format(self):
        """Hash is valid SHA-256 hex string."""
        content = load_prompt_template("session_synthesis_prompt.txt")
        h = prompt_hash(content)
        assert len(h) == 64
        assert all(c in "0123456789abcdef" for c in h)

    def test_template_has_role_labels(self):
        """Template documents role name mappings."""
        content = load_prompt_template("session_synthesis_prompt.txt")
        assert "선생님" in content
        assert "지수(학생)" in content
        assert "엔토(멘토)" in content

    def test_template_has_json_schema(self):
        """Template specifies the output JSON schema."""
        content = load_prompt_template("session_synthesis_prompt.txt")
        assert "brief_feedback" in content
        assert "strengths" in content
        assert "improvements" in content
        assert "dialogue_coaching" in content
        assert "message_id" in content
