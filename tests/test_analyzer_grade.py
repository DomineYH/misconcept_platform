"""Tests for grade derivation in analyzer pipeline."""

import json
from unittest.mock import Mock

from src.models.analysis_framework import AnalysisFramework
from src.models.question_analysis import QuestionAnalysis


def _make_framework(labels_json: str):
    fw = Mock(spec=AnalysisFramework)
    fw.labels_json = labels_json
    fw.labels_grade_map = AnalysisFramework.labels_grade_map.fget(fw)
    return fw


class TestGradeDerivation:
    """Grade is derived from framework.labels_grade_map after classification."""

    def test_grade_derived_from_label_high(self):
        fw = _make_framework(
            json.dumps(
                [
                    {"name": "A", "criteria": "", "level": "high"},
                    {"name": "B", "criteria": ""},
                ]
            )
        )
        grade_map = fw.labels_grade_map
        assert grade_map.get("A") == "우수"

    def test_grade_derived_from_label_low(self):
        fw = _make_framework(
            json.dumps(
                [
                    {"name": "A", "criteria": "", "level": "low"},
                    {"name": "B", "criteria": ""},
                ]
            )
        )
        grade_map = fw.labels_grade_map
        assert grade_map.get("A") == "개선"

    def test_grade_none_when_label_has_no_level(self):
        fw = _make_framework(
            json.dumps(
                [
                    {"name": "A", "criteria": ""},
                    {"name": "B", "criteria": ""},
                ]
            )
        )
        grade_map = fw.labels_grade_map
        assert grade_map.get("A") is None

    def test_question_analysis_persists_grade(self):
        """QuestionAnalysis model accepts grade field."""
        qa = QuestionAnalysis(
            message_id=1,
            label="high_leverage",
            confidence=0.9,
            meta_json=None,
            grade="우수",
        )
        assert qa.grade == "우수"
        assert qa.label == "high_leverage"

    def test_question_analysis_grade_default_none(self):
        """QuestionAnalysis grade defaults to None."""
        qa = QuestionAnalysis(
            message_id=1,
            label="high_leverage",
            confidence=0.9,
            meta_json=None,
        )
        assert qa.grade is None
