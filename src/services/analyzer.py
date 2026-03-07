"""
Analyzer service for teacher question classification (T060).

Stateless LLM-based classification using framework-specific
prompts with structured JSON output.
"""

import json
import logging
from typing import Dict, Optional

from openai import APIConnectionError, APIError, AsyncOpenAI, RateLimitError
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from src.config import config
from src.models.analysis_framework import AnalysisFramework
from src.prompts.example_templates import generate_examples
from src.utils.cache import load_prompt_template
from src.utils.openai_helpers import extract_response_text

logger = logging.getLogger(__name__)


class Analyzer:
    """
    Question classification service using OpenAI Responses API.

    Supports GPT-5 and GPT-4 models via Responses API (GPT-3.5 not supported).

    Attributes:
        client: Async OpenAI client
        model: Model identifier (GPT-5 or GPT-4)
        temperature: Deprecated (Responses API uses fixed temperature)
    """

    def __init__(self):
        """Initialize analyzer with OpenAI client."""
        self.client = AsyncOpenAI(api_key=config.OPENAI_API_KEY)
        self.model = config.ANALYSIS_MODEL or "gpt-5"
        self.reasoning_effort = config.ANALYSIS_REASONING
        # Load cached prompt templates (T111 optimization)
        self.prompt_template = load_prompt_template("analysis_prompt.txt")
        self.greeting_template = load_prompt_template("greeting_detection.txt")

    def _normalize_reasoning(self, reasoning: any) -> dict:
        """
        Normalize reasoning to structured format for backward compatibility.

        Args:
            reasoning: Raw reasoning from LLM (string or dict)

        Returns:
            Structured reasoning dict with all required keys
        """
        if isinstance(reasoning, str):
            # Legacy format - convert to new structure
            return {
                "summary": reasoning,
                "pedagogical": None,
                "cognitive": None,
                "contextual": None,
            }
        elif isinstance(reasoning, dict):
            # Ensure all keys exist with proper structure
            return {
                "summary": reasoning.get("summary", ""),
                "pedagogical": reasoning.get("pedagogical"),
                "cognitive": reasoning.get("cognitive"),
                "contextual": reasoning.get("contextual"),
            }
        return {
            "summary": str(reasoning) if reasoning else "",
            "pedagogical": None,
            "cognitive": None,
            "contextual": None,
        }

    @retry(
        retry=retry_if_exception_type(
            (APIConnectionError, APIError, RateLimitError)
        ),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
    )
    async def classify_question(
        self,
        question: str,
        framework: AnalysisFramework,
        context: Optional[str] = None,
        scenario_title: Optional[str] = None,
        misconception_prompt: Optional[str] = None,
        student_profile: Optional[str] = None,
    ) -> Dict[str, any]:
        """
        Classify a teacher question using the analysis framework.

        Args:
            question: Teacher's question text
            framework: Analysis framework with labels
            context: Optional conversation context (previous messages)
            scenario_title: Optional scenario title for context
            misconception_prompt: Optional misconception being addressed
            student_profile: Optional student profile/persona

        Returns:
            Dict with keys: label, confidence, reasoning

        Raises:
            ValueError: If response format is invalid
            APIError: If OpenAI API call fails after retries
        """
        # Generate dynamic few-shot examples
        few_shot_examples = generate_examples(
            framework.labels,
            framework.description or "",
        )

        # Build criteria-formatted labels for prompt
        criteria_map = framework.label_criteria_map
        labels_with_criteria = "\n".join(
            f"- **{name}**: {criteria}" if criteria else f"- **{name}**"
            for name, criteria in criteria_map.items()
        )
        label_names = framework.label_names

        # Format prompt with framework and scenario context
        prompt = self.prompt_template.format(
            framework_name=framework.name,
            framework_description=(framework.description or ""),
            framework_labels=", ".join(label_names),
            framework_labels_with_criteria=(labels_with_criteria),
            few_shot_examples=few_shot_examples,
            scenario_title=(scenario_title or "Not specified"),
            misconception_prompt=(misconception_prompt or "Not specified"),
            student_profile=(student_profile or "Not specified"),
            question=question,
            context=context or "No prior context",
        )

        try:
            # OpenAI Responses API 호출 (GPT-5 호환)
            # GPT-5 models use temperature=1.0 (default, not configurable)
            # For GPT-4/3.5: temperature is ignored in Responses API

            # Build input (user role)
            input_messages = [{"role": "user", "content": prompt}]

            response = await self.client.responses.create(
                model=self.model,
                input=input_messages,
                max_output_tokens=1500,  # Increased for structured reasoning
                reasoning={"effort": self.reasoning_effort},
            )

            # Parse JSON response (GPT-5 structure)
            content = extract_response_text(response)
            result = json.loads(content)

            # Validate response structure
            if not all(k in result for k in ["label", "confidence"]):
                raise ValueError(
                    "Invalid response format: missing required fields"
                )

            # Validate label is in framework
            if result["label"] not in label_names:
                logger.warning(
                    "LLM returned invalid label "
                    f"'{result['label']}', "
                    "using first framework label"
                )
                result["label"] = label_names[0]

            # Validate confidence range
            confidence = float(result["confidence"])
            if not 0.0 <= confidence <= 1.0:
                logger.warning(
                    f"Invalid confidence {confidence}, clamping to [0,1]"
                )
                result["confidence"] = max(0.0, min(1.0, confidence))

            # Normalize reasoning to structured format
            result["reasoning"] = self._normalize_reasoning(
                result.get("reasoning", "")
            )

            return result

        except json.JSONDecodeError as e:
            logger.error("Failed to parse JSON response: %s", e)
            raise ValueError(f"Invalid JSON in LLM response: {e}")
        except (APIConnectionError, RateLimitError, APIError) as e:
            logger.error("Analyzer API error: %s: %s", type(e).__name__, str(e))
            raise
        except Exception as e:
            logger.error("Classification failed: %s", e)
            raise

    async def batch_classify(
        self,
        questions: list[str],
        framework: AnalysisFramework,
        context: Optional[str] = None,
        scenario_title: Optional[str] = None,
        misconception_prompt: Optional[str] = None,
        student_profile: Optional[str] = None,
    ) -> list[Dict[str, any]]:
        """
        Classify multiple questions sequentially.

        Args:
            questions: List of teacher questions
            framework: Analysis framework
            context: Optional shared context
            scenario_title: Optional scenario title for context
            misconception_prompt: Optional misconception being addressed
            student_profile: Optional student profile/persona

        Returns:
            List of classification results
        """
        results = []
        for question in questions:
            try:
                result = await self.classify_question(
                    question=question,
                    framework=framework,
                    context=context,
                    scenario_title=scenario_title,
                    misconception_prompt=misconception_prompt,
                    student_profile=student_profile,
                )
                results.append(result)
            except Exception as e:
                logger.error(
                    "Failed to classify question '%s': %s", question, e
                )
                # Return default classification on failure
                results.append(
                    {
                        "label": framework.label_names[0],
                        "confidence": 0.0,
                        "reasoning": (f"Classification failed: {e}"),
                    }
                )
        return results

    @retry(
        retry=retry_if_exception_type(
            (APIConnectionError, APIError, RateLimitError)
        ),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
    )
    async def detect_greetings(
        self, messages: list[str]
    ) -> list[Dict[str, any]]:
        """
        Detect greeting messages using LLM.

        Args:
            messages: List of teacher message contents

        Returns:
            List of dicts with keys: index, is_greeting, reason

        Example:
            [
                {"index": 0, "is_greeting": True, "reason": "Opening greeting"},
                {"index": 1, "is_greeting": False,
                 "reason": "Conceptual question"}
            ]
        """
        if not messages:
            return []

        # Format messages for prompt
        formatted_messages = "\n".join(
            f"{i}. {msg}" for i, msg in enumerate(messages)
        )
        prompt = self.greeting_template.format(messages=formatted_messages)

        try:
            response = await self.client.responses.create(
                model=self.model,
                input=[{"role": "user", "content": prompt}],
                max_output_tokens=500,
                reasoning={"effort": self.reasoning_effort},
            )

            content = extract_response_text(response)
            results = json.loads(content)

            # Validate response structure
            if not isinstance(results, list):
                raise ValueError("Response must be a JSON array")

            # Ensure all indices are covered
            validated_results = []
            result_map = {r.get("index"): r for r in results}

            for i in range(len(messages)):
                if i in result_map:
                    validated_results.append(result_map[i])
                else:
                    # Default to non-greeting if missing
                    validated_results.append(
                        {
                            "index": i,
                            "is_greeting": False,
                            "reason": "Not classified",
                        }
                    )

            return validated_results

        except json.JSONDecodeError as e:
            logger.warning("Greeting detection JSON parse error: %s", e)
            # Return safe defaults (assume no greetings)
            return [
                {"index": i, "is_greeting": False, "reason": "Parse error"}
                for i in range(len(messages))
            ]
        except Exception as e:
            logger.warning("Greeting detection failed: %s", e)
            # Return safe defaults (assume no greetings)
            return [
                {"index": i, "is_greeting": False, "reason": "Detection failed"}
                for i in range(len(messages))
            ]
