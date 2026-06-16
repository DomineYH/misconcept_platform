from __future__ import annotations

from typing import Final, TypeAlias

JsonValue: TypeAlias = (
    str | int | float | bool | None | list["JsonValue"] | dict[str, "JsonValue"]
)
TextFormat: TypeAlias = dict[str, JsonValue]

CLASSIFICATION_TEXT_FORMAT: Final[TextFormat] = {
    "format": {
        "type": "json_schema",
        "name": "question_classification",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": {
                "label": {"type": "string"},
                "confidence": {"type": "number"},
                "reasoning": {
                    "type": "object",
                    "properties": {
                        "summary": {"type": "string"},
                        "improved_sentence": {
                            "type": ["string", "null"],
                        },
                    },
                    "required": ["summary", "improved_sentence"],
                    "additionalProperties": False,
                },
            },
            "required": ["label", "confidence", "reasoning"],
            "additionalProperties": False,
        },
    }
}

GREETING_TEXT_FORMAT: Final[TextFormat] = {
    "format": {
        "type": "json_schema",
        "name": "greeting_detection",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": {
                "results": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "index": {"type": "integer"},
                            "is_greeting": {"type": "boolean"},
                            "reason": {"type": "string"},
                        },
                        "required": ["index", "is_greeting", "reason"],
                        "additionalProperties": False,
                    },
                }
            },
            "required": ["results"],
            "additionalProperties": False,
        },
    }
}
