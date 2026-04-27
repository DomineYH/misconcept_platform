"""Tests for framework label level validation and grade mapping."""

import json
from unittest.mock import Mock

import pytest
from pydantic import ValidationError

from src.api.schemas import LabelItem
from src.models.analysis_framework import AnalysisFramework

# ---------------------------------------------------------------------------
# LabelItem schema validation
# ---------------------------------------------------------------------------


class TestLabelItemLevel:
    """LabelItem accepts level='high'/'low'/None, rejects others."""

    def test_level_high_valid(self):
        item = LabelItem(name="test", criteria="c", level="high")
        assert item.level == "high"

    def test_level_low_valid(self):
        item = LabelItem(name="test", criteria="c", level="low")
        assert item.level == "low"

    def test_level_none_valid(self):
        item = LabelItem(name="test", criteria="c", level=None)
        assert item.level is None

    def test_level_omitted_defaults_none(self):
        item = LabelItem(name="test", criteria="c")
        assert item.level is None

    def test_level_invalid_rejected(self):
        with pytest.raises(ValidationError):
            LabelItem(name="test", criteria="c", level="medium")


# ---------------------------------------------------------------------------
# Model validate_labels_json
# ---------------------------------------------------------------------------


class TestValidateLabelsJson:
    """analysis_framework.validate_labels_json rejects invalid level values."""

    def _make_framework(self):
        return AnalysisFramework.__new__(AnalysisFramework)

    def test_dict_with_valid_level_passes(self):
        fw = self._make_framework()
        labels = json.dumps(
            [
                {"name": "A", "criteria": "c1", "level": "high"},
                {"name": "B", "criteria": "c2", "level": "low"},
            ]
        )
        result = fw.validate_labels_json("labels_json", labels)
        assert result == labels

    def test_dict_with_invalid_level_rejected(self):
        fw = self._make_framework()
        labels = json.dumps(
            [
                {"name": "A", "criteria": "c1", "level": "medium"},
                {"name": "B", "criteria": "c2"},
            ]
        )
        with pytest.raises(ValueError, match="level must be"):
            fw.validate_labels_json("labels_json", labels)

    def test_dict_with_null_level_passes(self):
        fw = self._make_framework()
        labels = json.dumps(
            [
                {"name": "A", "criteria": "c1", "level": None},
                {"name": "B", "criteria": "c2"},
            ]
        )
        result = fw.validate_labels_json("labels_json", labels)
        assert result == labels

    def test_dict_without_level_key_passes(self):
        fw = self._make_framework()
        labels = json.dumps(
            [
                {"name": "A", "criteria": "c1"},
                {"name": "B", "criteria": "c2"},
            ]
        )
        result = fw.validate_labels_json("labels_json", labels)
        assert result == labels


# ---------------------------------------------------------------------------
# labels_grade_map property
# ---------------------------------------------------------------------------


class TestLabelsGradeMap:
    """labels_grade_map returns correct grade for each level."""

    def _make_framework(self, labels_json: str):
        fw = Mock(spec=AnalysisFramework)
        fw.labels_json = labels_json
        # Bind the real property from the class
        fw.labels_grade_map = AnalysisFramework.labels_grade_map.fget(fw)
        return fw

    def test_grade_map_high_to_excellent(self):
        fw = self._make_framework(
            json.dumps(
                [
                    {"name": "A", "criteria": "", "level": "high"},
                    {"name": "B", "criteria": ""},
                ]
            )
        )
        assert fw.labels_grade_map == {"A": "우수", "B": None}

    def test_grade_map_low_to_improve(self):
        fw = self._make_framework(
            json.dumps(
                [
                    {"name": "B", "criteria": "", "level": "low"},
                    {"name": "C", "criteria": ""},
                ]
            )
        )
        assert fw.labels_grade_map == {"B": "개선", "C": None}

    def test_grade_map_null_level_returns_none(self):
        fw = self._make_framework(
            json.dumps(
                [
                    {"name": "C", "criteria": "", "level": None},
                    {"name": "D", "criteria": ""},
                ]
            )
        )
        assert fw.labels_grade_map == {"C": None, "D": None}

    def test_grade_map_missing_level_returns_none(self):
        fw = self._make_framework(
            json.dumps(
                [
                    {"name": "C", "criteria": ""},
                    {"name": "D", "criteria": ""},
                ]
            )
        )
        assert fw.labels_grade_map == {"C": None, "D": None}

    def test_legacy_flat_labels_grade_map_returns_none(self):
        fw = self._make_framework(json.dumps(["X", "Y"]))
        assert fw.labels_grade_map == {"X": None, "Y": None}

    def test_grade_map_mixed_levels(self):
        fw = self._make_framework(
            json.dumps(
                [
                    {"name": "A", "criteria": "", "level": "high"},
                    {"name": "B", "criteria": "", "level": "low"},
                    {"name": "C", "criteria": ""},
                ]
            )
        )
        assert fw.labels_grade_map == {"A": "우수", "B": "개선", "C": None}
