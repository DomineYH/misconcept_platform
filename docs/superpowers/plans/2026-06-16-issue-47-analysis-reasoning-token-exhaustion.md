# Issue 47 Analysis Reasoning Token Exhaustion Fix Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stop end-session analysis from dropping teacher messages when OpenAI Responses API reasoning consumes the configured output token budget.

**Architecture:** Split analysis LLM settings so classification, greeting detection, and synthesis do not all inherit one `ANALYSIS_REASONING` value. Add a typed incomplete-response path in the OpenAI helper, then let `Analyzer` retry one `status=incomplete`/`max_output_tokens` response with the configured retry budget. Persist failed classifications as explicit degraded `QuestionAnalysis` rows with a visible label and metadata so distribution, synthesis input, CSV export, and admin inspection do not silently miss messages.

**Tech Stack:** Python 3.11, FastAPI service layer, SQLAlchemy async ORM, Pydantic v2 settings, OpenAI Responses API, pytest, Black, Ruff

---

## Context

Issue: https://github.com/DomineYH/misconcept_platform/issues/47

Official API behavior checked while writing this plan:

- Reasoning models can return `response.status == "incomplete"` with `incomplete_details.reason == "max_output_tokens"`; if no `output_text` exists, the run can have spent the budget during reasoning.
  Source: https://developers.openai.com/api/docs/guides/reasoning#allocating-space-for-reasoning
- Responses API structured outputs are supplied with `text: { format: { type: "json_schema", strict: true, schema: ... } }`.
  Source: https://developers.openai.com/api/docs/guides/structured-outputs

Current code paths:

- `src/services/analyzer.py` hardcodes `max_output_tokens=1500` for classification and `500` for greeting detection, both with `config.ANALYSIS_REASONING`.
- `src/services/session_synthesizer.py` also uses `config.ANALYSIS_REASONING`.
- `src/utils/openai_helpers.py` raises a generic `ValueError` when an incomplete response has no text.
- `src/services/analysis_pipeline.py` logs classification exceptions and `continue`s, so no `QuestionAnalysis` row is created for that teacher message.

Implementation decision:

- Do not add a database migration. `QuestionAnalysis.label` is already a free text column and `meta_json` can carry the degraded status.
- Use `label="분류 실패"` and `confidence=0.0` for degraded classification rows. This avoids pretending the message belongs to the first framework label and makes the count visible in the existing chart/export surfaces.
- Leave `src/services/misconception_analyzer.py` on the legacy `ANALYSIS_REASONING` path because issue #47 is scoped to end-session question classification, greeting filtering, and session synthesis.

## File Structure

- Modify: `src/config.py`
  - Add independent reasoning and token settings for classification, greeting detection, and synthesis.
  - Extend validators so new reasoning values and token limits are validated with existing settings.
- Modify: `src/utils/openai_helpers.py`
  - Add `IncompleteResponseError`, still a `ValueError`.
  - Include optional `reasoning_tokens` in `extract_usage_dict()` when Responses API usage details expose it.
- Modify: `src/services/analyzer.py`
  - Use the new config fields.
  - Add strict JSON schema `text.format` for classification and greeting detection.
  - Retry one incomplete/no-text response with the retry token budget.
- Modify: `src/services/session_synthesizer.py`
  - Use `ANALYSIS_SYNTHESIS_REASONING`.
- Modify: `src/prompts/greeting_detection.txt`
  - Match the greeting structured-output schema by requesting an object with a `results` array.
- Modify: `src/services/analysis_pipeline.py`
  - Persist degraded `QuestionAnalysis` rows instead of dropping failed classifications.
- Modify: `tests/unit/test_config.py`
  - Add config validation coverage for new settings.
- Modify: `tests/unit/test_openai_helpers.py`
  - Add typed incomplete-response and reasoning-token extraction coverage.
- Modify: `tests/unit/test_analyzer.py`
  - Add config/structured-output/retry tests for classification and greeting detection.
- Modify: `tests/integration/test_analysis_pipeline_e2e.py`
  - Add degraded classification persistence coverage.

No runtime database file should be edited.

---

### Task 1: Split Analysis LLM Configuration

**Files:**
- Modify: `tests/unit/test_config.py`
- Modify: `src/config.py`
- Modify: `src/services/session_synthesizer.py`

- [ ] **Step 1: Write failing config tests**

Append this class to `tests/unit/test_config.py`:

```python


class TestAnalysisLLMConfig:
    """Tests for issue #47 analysis-specific LLM settings."""

    def test_analysis_llm_defaults_are_split(self):
        """Classification/greeting/synthesis should not share one setting."""
        with patch.dict(
            "os.environ",
            {
                "OPENAI_API_KEY": "sk-test-key-123",
                "SESSION_SECRET": "test-secret-value-for-unit-tests-32x",
            },
        ):
            from importlib import reload

            import src.config

            reload(src.config)
            c = src.config.Config()

            assert c.ANALYSIS_REASONING == "high"
            assert c.ANALYSIS_CLASSIFICATION_REASONING == "low"
            assert c.ANALYSIS_GREETING_REASONING == "low"
            assert c.ANALYSIS_SYNTHESIS_REASONING == "high"
            assert c.ANALYSIS_CLASSIFICATION_MAX_TOKENS == 2500
            assert c.ANALYSIS_CLASSIFICATION_RETRY_MAX_TOKENS == 4000
            assert c.ANALYSIS_GREETING_MAX_TOKENS == 1000
            assert c.ANALYSIS_GREETING_RETRY_MAX_TOKENS == 1500

    def test_analysis_llm_settings_can_be_overridden(self):
        """New env vars should override only their matching operation."""
        with patch.dict(
            "os.environ",
            {
                "OPENAI_API_KEY": "sk-test-key-123",
                "SESSION_SECRET": "test-secret-value-for-unit-tests-32x",
                "ANALYSIS_REASONING": "high",
                "ANALYSIS_CLASSIFICATION_REASONING": "minimal",
                "ANALYSIS_GREETING_REASONING": "none",
                "ANALYSIS_SYNTHESIS_REASONING": "medium",
                "ANALYSIS_CLASSIFICATION_MAX_TOKENS": "3000",
                "ANALYSIS_CLASSIFICATION_RETRY_MAX_TOKENS": "5000",
                "ANALYSIS_GREETING_MAX_TOKENS": "900",
                "ANALYSIS_GREETING_RETRY_MAX_TOKENS": "1800",
            },
        ):
            from importlib import reload

            import src.config

            reload(src.config)
            c = src.config.Config()

            assert c.ANALYSIS_REASONING == "high"
            assert c.ANALYSIS_CLASSIFICATION_REASONING == "minimal"
            assert c.ANALYSIS_GREETING_REASONING == "none"
            assert c.ANALYSIS_SYNTHESIS_REASONING == "medium"
            assert c.ANALYSIS_CLASSIFICATION_MAX_TOKENS == 3000
            assert c.ANALYSIS_CLASSIFICATION_RETRY_MAX_TOKENS == 5000
            assert c.ANALYSIS_GREETING_MAX_TOKENS == 900
            assert c.ANALYSIS_GREETING_RETRY_MAX_TOKENS == 1800

    def test_analysis_token_limits_must_be_positive(self):
        """New analysis token budgets should reject zero and negative values."""
        from importlib import reload

        import src.config

        with patch.dict(
            "os.environ",
            {
                "OPENAI_API_KEY": "sk-test-key-123",
                "SESSION_SECRET": "test-secret-value-for-unit-tests-32x",
                "ANALYSIS_CLASSIFICATION_MAX_TOKENS": "0",
            },
        ):
            with pytest.raises(Exception):
                reload(src.config)
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
pytest tests/unit/test_config.py::TestAnalysisLLMConfig -v
```

Expected: FAIL with an `AttributeError` or Pydantic validation error referencing missing `ANALYSIS_CLASSIFICATION_REASONING`.

- [ ] **Step 3: Add config fields and validators**

In `src/config.py`, replace the reasoning and bot-token block at lines 29-41 with:

```python
    # ===== GPT-5 Reasoning Effort Configuration =====
    # Valid values: none, minimal, low, medium, high
    # ANALYSIS_REASONING is kept for legacy callers that have not moved to
    # operation-specific analysis settings.
    ANALYSIS_REASONING: str = "high"
    ANALYSIS_CLASSIFICATION_REASONING: str = "low"
    ANALYSIS_GREETING_REASONING: str = "low"
    ANALYSIS_SYNTHESIS_REASONING: str = "high"
    STUDENT_REASONING: str = "medium"
    TUTOR_REASONING: str = "low"

    # ===== Bot Token Limits =====
    # Note: GPT-5 reasoning tokens count toward max_output_tokens.
    # gpt-5-mini "low" can use ~450 reasoning tokens alone.
    # Minimum recommended: 500 (reasoning) + 500 (text) = 1000
    STUDENT_MAX_TOKENS: int = 1500
    TUTOR_MAX_TOKENS: int = 1500
    ANALYSIS_CLASSIFICATION_MAX_TOKENS: int = 2500
    ANALYSIS_CLASSIFICATION_RETRY_MAX_TOKENS: int = 4000
    ANALYSIS_GREETING_MAX_TOKENS: int = 1000
    ANALYSIS_GREETING_RETRY_MAX_TOKENS: int = 1500
    TUTOR_INTERVENTION_THRESHOLD: int = 3
```

In `src/config.py`, replace the `validate_reasoning` decorator at lines 131-133 with:

```python
    @field_validator(
        "ANALYSIS_REASONING",
        "ANALYSIS_CLASSIFICATION_REASONING",
        "ANALYSIS_GREETING_REASONING",
        "ANALYSIS_SYNTHESIS_REASONING",
        "STUDENT_REASONING",
        "TUTOR_REASONING",
    )
```

In `src/config.py`, replace the `validate_positive_tokens` decorator at lines 147-148 with:

```python
    @field_validator(
        "STUDENT_MAX_TOKENS",
        "TUTOR_MAX_TOKENS",
        "ANALYSIS_CLASSIFICATION_MAX_TOKENS",
        "ANALYSIS_CLASSIFICATION_RETRY_MAX_TOKENS",
        "ANALYSIS_GREETING_MAX_TOKENS",
        "ANALYSIS_GREETING_RETRY_MAX_TOKENS",
    )
```

- [ ] **Step 4: Move synthesis to its dedicated reasoning config**

In `src/services/session_synthesizer.py`, replace:

```python
        self.reasoning_effort = config.ANALYSIS_REASONING
```

with:

```python
        self.reasoning_effort = config.ANALYSIS_SYNTHESIS_REASONING
```

- [ ] **Step 5: Run config tests to verify they pass**

Run:

```bash
pytest tests/unit/test_config.py::TestAnalysisLLMConfig -v
```

Expected: 3 PASS.

- [ ] **Step 6: Commit**

```bash
git add src/config.py src/services/session_synthesizer.py tests/unit/test_config.py
git commit -m "fix: split analysis llm budgets by operation"
```

---

### Task 2: Add Typed Incomplete Response Handling

**Files:**
- Modify: `tests/unit/test_openai_helpers.py`
- Modify: `src/utils/openai_helpers.py`

- [ ] **Step 1: Write failing helper tests**

In `tests/unit/test_openai_helpers.py`, replace the import:

```python
from src.utils.openai_helpers import extract_response_text, extract_usage_dict
```

with:

```python
from src.utils.openai_helpers import (
    IncompleteResponseError,
    extract_response_text,
    extract_usage_dict,
)
```

Append these tests to `tests/unit/test_openai_helpers.py`:

```python


def test_extract_response_text_incomplete_without_text_raises_typed_error():
    """Incomplete responses without visible text should expose the reason."""
    response = Mock()
    response.status = "incomplete"
    response.incomplete_details = {"reason": "max_output_tokens"}
    response.output = []
    response.output_text = None

    with pytest.raises(IncompleteResponseError) as exc:
        extract_response_text(response)

    assert exc.value.reason == "max_output_tokens"
    assert "max_output_tokens" in str(exc.value)


def test_extract_usage_dict_includes_reasoning_tokens_from_object_details():
    """Responses usage details should preserve reasoning token count."""
    details = Mock()
    details.reasoning_tokens = 64
    usage = Mock()
    usage.input_tokens = 100
    usage.output_tokens = 80
    usage.total_tokens = 180
    usage.output_tokens_details = details
    response = Mock()
    response.usage = usage

    result = extract_usage_dict(response)

    assert result == {
        "prompt_tokens": 100,
        "completion_tokens": 80,
        "total_tokens": 180,
        "reasoning_tokens": 64,
    }


def test_extract_usage_dict_includes_reasoning_tokens_from_dict_details():
    """Serialized usage details should preserve reasoning token count."""
    response = Mock()
    response.usage = {
        "input_tokens": 20,
        "output_tokens": 12,
        "total_tokens": 32,
        "output_tokens_details": {"reasoning_tokens": 9},
    }

    result = extract_usage_dict(response)

    assert result == {
        "prompt_tokens": 20,
        "completion_tokens": 12,
        "total_tokens": 32,
        "reasoning_tokens": 9,
    }
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
pytest tests/unit/test_openai_helpers.py -v
```

Expected: FAIL with `ImportError: cannot import name 'IncompleteResponseError'`.

- [ ] **Step 3: Implement typed error and reasoning-token extraction**

In `src/utils/openai_helpers.py`, add this class after `logger = logging.getLogger(__name__)`:

```python

class IncompleteResponseError(ValueError):
    """Raised when a Responses API result is incomplete and has no text."""

    def __init__(self, reason: str | None) -> None:
        self.reason = reason
        detail = reason or "unknown"
        super().__init__(
            "Response incomplete and contained no extractable text "
            f"(reason: {detail}). Increase max_output_tokens for "
            "GPT-5 reasoning."
        )
```

In `src/utils/openai_helpers.py`, add this helper before `extract_usage_dict()`:

```python

def _extract_int(candidate: Any, key: str) -> int | None:
    """Extract an integer field from dict-like or object-like structures."""
    if candidate is None:
        return None
    if isinstance(candidate, dict):
        value = candidate.get(key)
    else:
        value = getattr(candidate, key, None)
    return value if isinstance(value, int) else None
```

In `src/utils/openai_helpers.py`, replace the return block in `extract_usage_dict()` at lines 106-110 with:

```python
    result = {
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": total_tokens,
    }

    details = (
        usage.get("output_tokens_details")
        if isinstance(usage, dict)
        else getattr(usage, "output_tokens_details", None)
    )
    reasoning_tokens = _extract_int(details, "reasoning_tokens")
    if reasoning_tokens is not None:
        result["reasoning_tokens"] = reasoning_tokens

    return result
```

In `src/utils/openai_helpers.py`, replace the incomplete branch at lines 261-265 with:

```python
    if is_incomplete:
        raise IncompleteResponseError(incomplete_reason)
```

- [ ] **Step 4: Run helper tests to verify they pass**

Run:

```bash
pytest tests/unit/test_openai_helpers.py -v
```

Expected: all tests in `tests/unit/test_openai_helpers.py` PASS.

- [ ] **Step 5: Commit**

```bash
git add src/utils/openai_helpers.py tests/unit/test_openai_helpers.py
git commit -m "fix: expose incomplete responses from openai helper"
```

---

### Task 3: Retry Analyzer Calls With Structured Responses

**Files:**
- Modify: `tests/unit/test_analyzer.py`
- Modify: `src/services/analyzer.py`
- Modify: `src/prompts/greeting_detection.txt`

- [ ] **Step 1: Write failing analyzer tests**

Append these helper functions near the top of `tests/unit/test_analyzer.py`, after the `analyzer` fixture:

```python


def response_with_content(content: str) -> Mock:
    """Create a simple Responses API mock with text content."""
    response = Mock()
    response.output = Mock(content=content)
    response.output_text = None
    response.usage = {
        "input_tokens": 10,
        "output_tokens": 5,
        "total_tokens": 15,
    }
    return response


def incomplete_response(reasoning_tokens: int = 1500) -> Mock:
    """Create an incomplete Responses API mock with no visible text."""
    response = Mock()
    response.status = "incomplete"
    response.incomplete_details = {"reason": "max_output_tokens"}
    response.output = []
    response.output_text = None
    response.usage = {
        "input_tokens": 100,
        "output_tokens": reasoning_tokens,
        "total_tokens": 100 + reasoning_tokens,
        "output_tokens_details": {"reasoning_tokens": reasoning_tokens},
    }
    return response
```

Append these tests to `tests/unit/test_analyzer.py`:

```python


@pytest.mark.asyncio
async def test_classify_question_uses_split_budget_and_structured_output(
    analyzer, mock_framework
):
    """Classification should use operation-specific config and JSON schema."""
    mock_response = response_with_content(
        '{"label": "Pressing", "confidence": 0.92, '
        '"reasoning": {"summary": "탐색 질문", "improved_sentence": null}}'
    )
    analyzer.client.responses.create = AsyncMock(return_value=mock_response)

    await analyzer.classify_question("왜 그렇게 생각했니?", mock_framework)

    kwargs = analyzer.client.responses.create.call_args.kwargs
    assert kwargs["max_output_tokens"] == analyzer.classification_max_tokens
    assert kwargs["reasoning"] == {
        "effort": analyzer.classification_reasoning_effort
    }
    assert kwargs["text"]["format"]["type"] == "json_schema"
    assert kwargs["text"]["format"]["name"] == "question_classification"
    assert kwargs["text"]["format"]["strict"] is True


@pytest.mark.asyncio
async def test_classify_question_retries_incomplete_without_text(
    analyzer, mock_framework
):
    """A max-output incomplete response should retry once with retry budget."""
    first_response = incomplete_response(reasoning_tokens=1500)
    second_response = response_with_content(
        '{"label": "Pressing", "confidence": 0.88, '
        '"reasoning": {"summary": "재시도 성공", "improved_sentence": null}}'
    )
    analyzer.client.responses.create = AsyncMock(
        side_effect=[first_response, second_response]
    )

    result = await analyzer.classify_question(
        "왜 분모끼리 더해도 된다고 생각했니?",
        mock_framework,
    )

    assert result["label"] == "Pressing"
    assert result["confidence"] == 0.88
    assert analyzer.client.responses.create.call_count == 2
    first_kwargs = analyzer.client.responses.create.call_args_list[0].kwargs
    second_kwargs = analyzer.client.responses.create.call_args_list[1].kwargs
    assert first_kwargs["max_output_tokens"] == (
        analyzer.classification_max_tokens
    )
    assert second_kwargs["max_output_tokens"] == (
        analyzer.classification_retry_max_tokens
    )
    assert result["_api_usage"] == {
        "prompt_tokens": 110,
        "completion_tokens": 1505,
        "total_tokens": 1620,
        "reasoning_tokens": 1500,
    }


@pytest.mark.asyncio
async def test_detect_greetings_uses_structured_object_response(analyzer):
    """Greeting detection should parse the schema object shape."""
    mock_response = response_with_content(
        '{"results": ['
        '{"index": 0, "is_greeting": true, "reason": "Opening greeting"},'
        '{"index": 1, "is_greeting": false, "reason": "Concept question"}'
        "]}"
    )
    analyzer.client.responses.create = AsyncMock(return_value=mock_response)

    results = await analyzer.detect_greetings(
        ["안녕하세요!", "분모가 다르면 어떻게 해야 할까요?"]
    )

    kwargs = analyzer.client.responses.create.call_args.kwargs
    assert kwargs["max_output_tokens"] == analyzer.greeting_max_tokens
    assert kwargs["reasoning"] == {
        "effort": analyzer.greeting_reasoning_effort
    }
    assert kwargs["text"]["format"]["name"] == "greeting_detection"
    assert results[0]["is_greeting"] is True
    assert results[1]["is_greeting"] is False


@pytest.mark.asyncio
async def test_detect_greetings_retries_incomplete_then_returns_result(
    analyzer,
):
    """Greeting detection should retry an incomplete no-text response once."""
    first_response = incomplete_response(reasoning_tokens=500)
    second_response = response_with_content(
        '{"results": ['
        '{"index": 0, "is_greeting": false, "reason": "Concept question"}'
        "]}"
    )
    analyzer.client.responses.create = AsyncMock(
        side_effect=[first_response, second_response]
    )

    results = await analyzer.detect_greetings(["왜 그렇게 생각했나요?"])

    assert analyzer.client.responses.create.call_count == 2
    first_kwargs = analyzer.client.responses.create.call_args_list[0].kwargs
    second_kwargs = analyzer.client.responses.create.call_args_list[1].kwargs
    assert first_kwargs["max_output_tokens"] == analyzer.greeting_max_tokens
    assert second_kwargs["max_output_tokens"] == (
        analyzer.greeting_retry_max_tokens
    )
    assert results == [
        {
            "index": 0,
            "is_greeting": False,
            "reason": "Concept question",
        }
    ]
    assert analyzer.last_greeting_usage == {
        "prompt_tokens": 110,
        "completion_tokens": 505,
        "total_tokens": 620,
        "reasoning_tokens": 500,
    }
```

- [ ] **Step 2: Run analyzer tests to verify they fail**

Run:

```bash
pytest tests/unit/test_analyzer.py::test_classify_question_uses_split_budget_and_structured_output tests/unit/test_analyzer.py::test_classify_question_retries_incomplete_without_text tests/unit/test_analyzer.py::test_detect_greetings_uses_structured_object_response tests/unit/test_analyzer.py::test_detect_greetings_retries_incomplete_then_returns_result -v
```

Expected: FAIL because `Analyzer` has no operation-specific budget attributes and does not pass `text=...`.

- [ ] **Step 3: Add structured output schemas and usage merge helper**

In `src/services/analyzer.py`, replace the OpenAI helper import at line 24:

```python
from src.utils.openai_helpers import extract_response_text, extract_usage_dict
```

with:

```python
from src.utils.openai_helpers import (
    IncompleteResponseError,
    extract_response_text,
    extract_usage_dict,
)
```

In `src/services/analyzer.py`, add these constants and helper after `logger = logging.getLogger(__name__)`:

```python

CLASSIFICATION_TEXT_FORMAT = {
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

GREETING_TEXT_FORMAT = {
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


def _merge_usage_dicts(
    *usages: dict[str, int] | None,
) -> dict[str, int] | None:
    """Merge usage dictionaries from an initial call and one retry."""
    merged: dict[str, int] = {}
    for usage in usages:
        if usage is None:
            continue
        for key, value in usage.items():
            if isinstance(value, int):
                merged[key] = merged.get(key, 0) + value
    return merged or None
```

- [ ] **Step 4: Update `Analyzer.__init__`**

In `src/services/analyzer.py`, replace lines 41-49 with:

```python
    def __init__(self):
        """Initialize analyzer with OpenAI client."""
        self.client = AsyncOpenAI(api_key=config.OPENAI_API_KEY)
        self.model = config.ANALYSIS_MODEL or "gpt-5"
        self.classification_reasoning_effort = (
            config.ANALYSIS_CLASSIFICATION_REASONING
        )
        self.greeting_reasoning_effort = config.ANALYSIS_GREETING_REASONING
        self.classification_max_tokens = (
            config.ANALYSIS_CLASSIFICATION_MAX_TOKENS
        )
        self.classification_retry_max_tokens = (
            config.ANALYSIS_CLASSIFICATION_RETRY_MAX_TOKENS
        )
        self.greeting_max_tokens = config.ANALYSIS_GREETING_MAX_TOKENS
        self.greeting_retry_max_tokens = (
            config.ANALYSIS_GREETING_RETRY_MAX_TOKENS
        )
        # Keep the old attribute for tests/manual scripts that inspect it.
        self.reasoning_effort = self.classification_reasoning_effort
        # Load cached prompt templates (T111 optimization)
        self.prompt_template = load_prompt_template("analysis_prompt.txt")
        self.greeting_template = load_prompt_template("greeting_detection.txt")
        self.last_greeting_usage: dict[str, int] | None = None
```

- [ ] **Step 5: Add one-retry response helper**

In `src/services/analyzer.py`, add this method after `_normalize_reasoning()`:

```python
    async def _create_response_text_with_incomplete_retry(
        self,
        *,
        input_messages: list[dict[str, str]],
        text_format: dict[str, Any],
        operation: str,
        max_output_tokens: int,
        retry_max_output_tokens: int,
        reasoning_effort: str,
    ) -> tuple[str, dict[str, int] | None]:
        """Create a response, retrying once when reasoning exhausts output."""
        response = await self.client.responses.create(
            model=self.model,
            input=input_messages,
            max_output_tokens=max_output_tokens,
            reasoning={"effort": reasoning_effort},
            text=text_format,
        )
        usage = extract_usage_dict(response)
        try:
            return extract_response_text(response), usage
        except IncompleteResponseError as e:
            reasoning_tokens = usage.get("reasoning_tokens") if usage else None
            logger.warning(
                "%s response incomplete; reason=%s max_output_tokens=%d "
                "reasoning_effort=%s reasoning_tokens=%s. Retrying with "
                "max_output_tokens=%d.",
                operation,
                e.reason,
                max_output_tokens,
                reasoning_effort,
                reasoning_tokens,
                retry_max_output_tokens,
            )

        retry_response = await self.client.responses.create(
            model=self.model,
            input=input_messages,
            max_output_tokens=retry_max_output_tokens,
            reasoning={"effort": reasoning_effort},
            text=text_format,
        )
        retry_usage = extract_usage_dict(retry_response)
        content = extract_response_text(retry_response)
        return content, _merge_usage_dicts(usage, retry_usage)
```

- [ ] **Step 6: Update `classify_question()` to use the helper**

In `src/services/analyzer.py`, replace lines 161-171:

```python
            response = await self.client.responses.create(
                model=self.model,
                input=input_messages,
                max_output_tokens=1500,  # Increased for structured reasoning
                reasoning={"effort": self.reasoning_effort},
            )
            api_usage = extract_usage_dict(response)

            # Parse JSON response (GPT-5 structure)
            content = extract_response_text(response)
            result = json.loads(content)
```

with:

```python
            content, api_usage = (
                await self._create_response_text_with_incomplete_retry(
                    input_messages=input_messages,
                    text_format=CLASSIFICATION_TEXT_FORMAT,
                    operation="classification",
                    max_output_tokens=self.classification_max_tokens,
                    retry_max_output_tokens=(
                        self.classification_retry_max_tokens
                    ),
                    reasoning_effort=self.classification_reasoning_effort,
                )
            )
            result = json.loads(content)
```

- [ ] **Step 7: Update `detect_greetings()` to use the helper and object shape**

In `src/services/analyzer.py`, replace lines 301-310:

```python
            response = await self.client.responses.create(
                model=self.model,
                input=[{"role": "user", "content": prompt}],
                max_output_tokens=500,
                reasoning={"effort": self.reasoning_effort},
            )
            self.last_greeting_usage = extract_usage_dict(response)

            content = extract_response_text(response)
            results = json.loads(content)
```

with:

```python
            content, self.last_greeting_usage = (
                await self._create_response_text_with_incomplete_retry(
                    input_messages=[{"role": "user", "content": prompt}],
                    text_format=GREETING_TEXT_FORMAT,
                    operation="greeting",
                    max_output_tokens=self.greeting_max_tokens,
                    retry_max_output_tokens=self.greeting_retry_max_tokens,
                    reasoning_effort=self.greeting_reasoning_effort,
                )
            )
            payload = json.loads(content)
            results = (
                payload.get("results")
                if isinstance(payload, dict)
                else payload
            )
```

- [ ] **Step 8: Update greeting prompt to match schema**

In `src/prompts/greeting_detection.txt`, replace the `## Response Format` section with:

```text
## Response Format

Return your analysis as a JSON object with a "results" array. Each item in
"results" should have:
- "index": The message number (0-based)
- "is_greeting": true if greeting/non-educational, false otherwise
- "reason": Brief explanation of your decision

Example response:
{
  "results": [
    {"index": 0, "is_greeting": true, "reason": "Opening greeting"},
    {"index": 1, "is_greeting": false, "reason": "Conceptual question about fractions"}
  ]
}

Analyze the messages now:
```

- [ ] **Step 9: Run focused analyzer tests to verify they pass**

Run:

```bash
pytest tests/unit/test_analyzer.py::test_classify_question_uses_split_budget_and_structured_output tests/unit/test_analyzer.py::test_classify_question_retries_incomplete_without_text tests/unit/test_analyzer.py::test_detect_greetings_uses_structured_object_response tests/unit/test_analyzer.py::test_detect_greetings_retries_incomplete_then_returns_result -v
```

Expected: 4 PASS.

- [ ] **Step 10: Run full analyzer tests**

Run:

```bash
pytest tests/unit/test_analyzer.py -v
```

Expected: all tests in `tests/unit/test_analyzer.py` PASS.

- [ ] **Step 11: Commit**

```bash
git add src/services/analyzer.py src/prompts/greeting_detection.txt tests/unit/test_analyzer.py
git commit -m "fix: retry incomplete analysis responses"
```

---

### Task 4: Persist Degraded Classification Rows

**Files:**
- Modify: `tests/integration/test_analysis_pipeline_e2e.py`
- Modify: `src/services/analysis_pipeline.py`

- [ ] **Step 1: Write failing integration test**

Append this test to `tests/integration/test_analysis_pipeline_e2e.py`:

```python


@pytest.mark.anyio
async def test_pipeline_persists_degraded_question_analysis_on_classify_failure(
    async_db_session,
    test_scenario,
    test_teacher,
    test_framework,
    greeting_mock,
    synthesis_mock,
    monkeypatch,
):
    """Failed classifications should remain visible in persisted analysis."""

    async def classify_question(self, **kwargs):
        question = kwargs["question"]
        if question.startswith("Why did"):
            raise ValueError(
                "Response incomplete and contained no extractable text "
                "(reason: max_output_tokens)."
            )
        return {
            "label": "Pressing",
            "confidence": 0.9,
            "reasoning": {"summary": "Test reasoning"},
        }

    monkeypatch.setattr(
        "src.services.analyzer.Analyzer.classify_question",
        classify_question,
    )

    session = await _seed_session(
        async_db_session, test_scenario, test_teacher
    )

    result = await analyze_session(
        session.id, session, test_scenario, test_framework, async_db_session
    )

    qa_rows = (
        (
            await async_db_session.execute(
                select(QuestionAnalysis).order_by(QuestionAnalysis.message_id)
            )
        )
        .scalars()
        .all()
    )
    assert len(qa_rows) == 2
    assert result["distribution"]["Pressing"] == 1
    assert result["distribution"]["분류 실패"] == 1

    degraded = next(row for row in qa_rows if row.label == "분류 실패")
    assert degraded.confidence == 0.0
    assert degraded.grade is None
    meta = json.loads(degraded.meta_json)
    assert meta == {
        "status": "degraded",
        "summary": "분류에 실패해 이 교사 메시지는 자동 분류되지 않았습니다.",
        "improved_sentence": None,
        "error_type": "ValueError",
        "error": (
            "Response incomplete and contained no extractable text "
            "(reason: max_output_tokens)."
        ),
    }

    synth_kwargs = synthesis_mock.call_args.kwargs
    qa_for_synthesis = synth_kwargs["question_analyses"]
    assert len(qa_for_synthesis) == 2
    assert any(
        qa["message_id"] == degraded.message_id
        and qa["label"] == "분류 실패"
        and '"status": "degraded"' in qa["reasoning"]
        for qa in qa_for_synthesis
    )
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
pytest tests/integration/test_analysis_pipeline_e2e.py::test_pipeline_persists_degraded_question_analysis_on_classify_failure -v
```

Expected: FAIL because only one `QuestionAnalysis` row is persisted and distribution has no `분류 실패` key.

- [ ] **Step 3: Add degraded row helper**

In `src/services/analysis_pipeline.py`, add this constant after `FALLBACK_FEEDBACK`:

```python
DEGRADED_CLASSIFICATION_LABEL = "분류 실패"
```

In `src/services/analysis_pipeline.py`, add this helper above `run_llm_pipeline()`:

```python

def _build_degraded_question_analysis(
    msg: Message,
    error: Exception,
) -> QuestionAnalysis:
    """Build a visible degraded analysis row for a failed classification."""
    meta = {
        "status": "degraded",
        "summary": (
            "분류에 실패해 이 교사 메시지는 자동 분류되지 않았습니다."
        ),
        "improved_sentence": None,
        "error_type": type(error).__name__,
        "error": str(error),
    }
    return QuestionAnalysis(
        message_id=msg.id,
        label=DEGRADED_CLASSIFICATION_LABEL,
        confidence=0.0,
        meta_json=json.dumps(meta, ensure_ascii=False),
        grade=None,
    )
```

- [ ] **Step 4: Persist degraded rows in the classification loop**

In `src/services/analysis_pipeline.py`, replace lines 188-191:

```python
        if isinstance(result, Exception):
            logger.warning(f"Failed to analyze message {msg.id}: {result}")
            continue
```

with:

```python
        if isinstance(result, Exception):
            logger.warning(f"Failed to analyze message {msg.id}: {result}")
            question_analyses.append(
                _build_degraded_question_analysis(msg, result)
            )
            distribution[DEGRADED_CLASSIFICATION_LABEL] = (
                distribution.get(DEGRADED_CLASSIFICATION_LABEL, 0) + 1
            )
            continue
```

In `src/services/analysis_pipeline.py`, replace line 216:

```python
        distribution[result["label"]] += 1
```

with:

```python
        distribution[result["label"]] = distribution.get(result["label"], 0) + 1
```

- [ ] **Step 5: Run degraded pipeline test to verify it passes**

Run:

```bash
pytest tests/integration/test_analysis_pipeline_e2e.py::test_pipeline_persists_degraded_question_analysis_on_classify_failure -v
```

Expected: 1 PASS.

- [ ] **Step 6: Run analysis pipeline integration tests**

Run:

```bash
pytest tests/integration/test_analysis_pipeline_e2e.py -v
```

Expected: all tests in `tests/integration/test_analysis_pipeline_e2e.py` PASS.

- [ ] **Step 7: Commit**

```bash
git add src/services/analysis_pipeline.py tests/integration/test_analysis_pipeline_e2e.py
git commit -m "fix: persist degraded classification results"
```

---

### Task 5: Verify the Complete Fix

**Files:**
- Verify: `src/config.py`
- Verify: `src/utils/openai_helpers.py`
- Verify: `src/services/analyzer.py`
- Verify: `src/services/session_synthesizer.py`
- Verify: `src/services/analysis_pipeline.py`
- Verify: `tests/unit/test_config.py`
- Verify: `tests/unit/test_openai_helpers.py`
- Verify: `tests/unit/test_analyzer.py`
- Verify: `tests/integration/test_analysis_pipeline_e2e.py`

- [ ] **Step 1: Run focused regression tests**

Run:

```bash
pytest tests/unit/test_config.py::TestAnalysisLLMConfig tests/unit/test_openai_helpers.py tests/unit/test_analyzer.py tests/integration/test_analysis_pipeline_e2e.py -v
```

Expected: PASS.

- [ ] **Step 2: Run format and lint checks for changed files**

Run:

```bash
black --check src/config.py src/utils/openai_helpers.py src/services/analyzer.py src/services/session_synthesizer.py src/services/analysis_pipeline.py tests/unit/test_config.py tests/unit/test_openai_helpers.py tests/unit/test_analyzer.py tests/integration/test_analysis_pipeline_e2e.py
```

Expected: `All done!`

Run:

```bash
ruff check src/config.py src/utils/openai_helpers.py src/services/analyzer.py src/services/session_synthesizer.py src/services/analysis_pipeline.py tests/unit/test_config.py tests/unit/test_openai_helpers.py tests/unit/test_analyzer.py tests/integration/test_analysis_pipeline_e2e.py
```

Expected: `All checks passed!`

- [ ] **Step 3: Run the project-level analysis test set named in issue #47**

Run:

```bash
pytest tests/unit/test_openai_helpers.py tests/unit/test_analyzer.py tests/integration/test_analysis_pipeline_e2e.py -v
```

Expected: PASS.

- [ ] **Step 4: Drive the fix through the application analysis surface**

Run the app with the local development database and a real `OPENAI_API_KEY` already exported in the shell:

```bash
uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
```

In the browser:

```text
1. Open http://localhost:8000.
2. Log in with a teacher account.
3. Start a scenario and send at least three substantive teacher messages.
4. End the session.
5. Trigger session analysis from the existing session analysis UI.
6. Confirm the analysis page/modal renders the distribution chart and feedback.
7. Confirm the server log does not repeat "Response incomplete and contained no extractable text" for the analyzed session.
```

In another shell, inspect the newest session analysis rows:

```bash
sqlite3 dialogue_sim.db "select m.session_id, qa.message_id, qa.label, qa.confidence, qa.meta_json from question_analysis qa join message m on m.id = qa.message_id where m.session_id = (select max(id) from \"session\") order by qa.message_id;"
```

Expected: one row for each non-greeting teacher message. If a classification exhausted output tokens twice, the row has `label='분류 실패'`, `confidence=0.0`, and `meta_json` contains `"status": "degraded"`.

- [ ] **Step 5: Commit verification-only prompt/doc adjustment if manual QA changed no code**

If Step 4 reveals no code changes, do not create a commit. If Step 4 reveals a small prompt wording correction in `src/prompts/greeting_detection.txt`, commit only that file:

```bash
git add src/prompts/greeting_detection.txt
git commit -m "fix: align greeting prompt with structured output"
```

---

## Self-Review

Spec coverage:

- Separate classification/greeting/synthesis settings: Task 1.
- Replace hardcoded classification and greeting token limits: Task 3.
- Retry incomplete classification responses with a larger budget: Task 3.
- Greeting incomplete path uses the same one-retry helper and then existing safe defaults if retry also fails: Task 3.
- Structured outputs reduce prompt-only JSON dependence: Task 3.
- Incomplete reason and reasoning token usage become observable in logs and merged usage data: Tasks 2 and 3.
- Failed classifications no longer disappear from persisted analysis or synthesis input: Task 4.
- Verification commands and manual analysis-surface check are explicit: Task 5.

Forbidden marker scan:

- No unresolved marker strings.
- No vague deferred-work markers.
- No undefined functions or methods referenced by later tasks.

Type consistency:

- New config names are identical across tests, `Config`, `Analyzer`, and `SessionSynthesizer`.
- `IncompleteResponseError.reason` is asserted in tests and logged in `Analyzer`.
- `DEGRADED_CLASSIFICATION_LABEL` is used for both persisted rows and distribution counts.
- Greeting structured output uses `{"results": [...]}` in schema, prompt, parser, and tests.
