"""Helper functions for analysis-related operations."""

import json
from typing import Optional


def parse_reasoning(meta_json: Optional[str]) -> Optional[dict]:
    """Parse meta_json to structured reasoning dict.

    Args:
        meta_json: JSON string containing reasoning information

    Returns:
        Dictionary with reasoning structure or None if no input
    """
    if not meta_json:
        return None
    try:
        return json.loads(meta_json)
    except json.JSONDecodeError:
        # Legacy string format
        return {
            "summary": meta_json,
            "pedagogical": None,
            "cognitive": None,
            "contextual": None,
        }
