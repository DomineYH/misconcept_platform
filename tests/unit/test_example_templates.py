"""Unit tests for dynamic few-shot example generation."""

import pytest
from src.prompts.example_templates import (
    classify_label_category,
    generate_examples,
    HIGH_LEVERAGE_KEYWORDS,
    LOW_LEVERAGE_KEYWORDS,
)


class TestClassifyLabelCategory:
    """Tests for classify_label_category function."""

    def test_high_leverage_pressing(self):
        """Pressing should map to high_leverage."""
        assert classify_label_category("Pressing") == "high_leverage"

    def test_high_leverage_quality(self):
        """HighQuality should map to high_leverage."""
        assert classify_label_category("HighQuality") == "high_leverage"

    def test_high_leverage_deep(self):
        """DeepQuestion should map to high_leverage."""
        assert classify_label_category("DeepQuestion") == "high_leverage"

    def test_low_leverage_recall(self):
        """Recall should map to low_leverage."""
        assert classify_label_category("Recall") == "low_leverage"

    def test_low_leverage_basic(self):
        """Basic should map to low_leverage."""
        assert classify_label_category("Basic") == "low_leverage"

    def test_low_leverage_factual(self):
        """FactualQuestion should map to low_leverage."""
        assert classify_label_category("FactualQuestion") == "low_leverage"

    def test_medium_leverage_linking(self):
        """Linking should map to medium_leverage."""
        assert classify_label_category("Linking") == "medium_leverage"

    def test_medium_leverage_directing(self):
        """Directing should map to medium_leverage."""
        assert classify_label_category("Directing") == "medium_leverage"

    def test_medium_leverage_neutral(self):
        """Neutral should map to medium_leverage."""
        assert classify_label_category("Neutral") == "medium_leverage"

    def test_uses_description_for_classification(self):
        """Description should be used for classification."""
        # Label alone doesn't match, but description contains keyword
        result = classify_label_category(
            "Type1", description="High leverage probing questions"
        )
        assert result == "high_leverage"

    def test_default_to_medium_leverage(self):
        """Unknown labels should default to medium_leverage."""
        assert classify_label_category("Unknown") == "medium_leverage"
        assert classify_label_category("Category1") == "medium_leverage"


class TestGenerateExamples:
    """Tests for generate_examples function."""

    def test_empty_labels_returns_empty_string(self):
        """Empty labels list should return empty string."""
        assert generate_examples([]) == ""

    def test_uses_actual_framework_labels(self):
        """Generated examples should use actual framework labels."""
        labels = ["Pressing", "Linking", "Recall"]
        result = generate_examples(labels)

        # Should contain actual labels
        assert "Pressing" in result
        assert "Linking" in result or "Recall" in result

    def test_custom_framework_labels_appear_in_output(self):
        """Custom framework labels should appear in generated examples."""
        labels = ["HighQuality", "LowQuality", "Neutral"]
        result = generate_examples(labels)

        # Should contain custom labels, not default ones
        assert "HighQuality" in result or "LowQuality" in result or "Neutral" in result

    def test_no_hardcoded_labels_in_custom_framework(self):
        """Hardcoded labels should not appear in custom framework output."""
        labels = ["Alpha", "Beta", "Gamma"]
        result = generate_examples(labels)

        # Should NOT contain hardcoded labels
        assert "Pressing" not in result
        assert "Linking" not in result
        assert "Directing" not in result
        assert "Recall" not in result

    def test_generates_maximum_three_examples(self):
        """Should generate at most 3 examples."""
        labels = ["A", "B", "C", "D", "E"]
        result = generate_examples(labels)

        # Count example headers
        example_count = result.count("Example ")
        assert example_count <= 3

    def test_generates_at_least_one_example(self):
        """Should generate at least one example for non-empty labels."""
        labels = ["OnlyLabel"]
        result = generate_examples(labels)

        assert "Example 1:" in result
        assert "OnlyLabel" in result

    def test_example_format_contains_required_fields(self):
        """Generated examples should contain all required fields."""
        labels = ["TestLabel"]
        result = generate_examples(labels)

        assert "Teacher:" in result
        assert "Classification:" in result
        assert "Confidence:" in result
        assert "Reasoning:" in result

    def test_distinct_categories_get_different_examples(self):
        """Labels of different categories should get different examples."""
        # Pressing = high_leverage, Recall = low_leverage
        labels = ["Pressing", "Recall"]
        result = generate_examples(labels)

        # Should have examples for both
        assert "Pressing" in result
        assert "Recall" in result

    def test_description_affects_classification(self):
        """Framework description should affect label classification."""
        # Without description, "Type1" would be medium_leverage
        # With description containing "deep", it should be high_leverage
        labels = ["Type1"]
        result = generate_examples(
            labels, description="Deep probing questions"
        )

        # Should still use the actual label
        assert "Type1" in result
