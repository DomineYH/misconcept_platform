"""
Analyzer service for teacher question classification (T060).

Stateless LLM-based classification using framework-specific
prompts with structured JSON output.
"""
import json
import logging
from typing import Dict, Optional

from openai import AsyncOpenAI, APIError, APIConnectionError, RateLimitError
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

from src.config import config
from src.models.analysis_framework import AnalysisFramework
from src.utils.cache import load_prompt_template


logger = logging.getLogger(__name__)


class Analyzer:
    """
    Question classification service using OpenAI GPT-3.5-turbo.

    Attributes:
        client: Async OpenAI client
        model: Model identifier (GPT-3.5-turbo)
        temperature: Low temperature for deterministic classification
    """

    def __init__(self):
        """Initialize analyzer with OpenAI client."""
        self.client = AsyncOpenAI(api_key=config.OPENAI_API_KEY)
        self.model = config.ANALYSIS_MODEL or "gpt-3.5-turbo"
        self.temperature = 0.2
        # Load cached prompt template (T111 optimization)
        self.prompt_template = load_prompt_template("analysis_prompt.txt")

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
    ) -> Dict[str, any]:
        """
        Classify a teacher question using the analysis framework.

        Args:
            question: Teacher's question text
            framework: Analysis framework with labels
            context: Optional conversation context (previous messages)

        Returns:
            Dict with keys: label, confidence, reasoning

        Raises:
            ValueError: If response format is invalid
            APIError: If OpenAI API call fails after retries
        """
        # Format prompt with framework and question
        prompt = self.prompt_template.format(
            framework_name=framework.name,
            framework_description=framework.description or "",
            framework_labels=", ".join(framework.labels),
            question=question,
            context=context or "No prior context",
        )

        try:
            # Call OpenAI API
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=self.temperature,
                response_format={"type": "json_object"},
            )

            # Parse JSON response
            content = response.choices[0].message.content
            result = json.loads(content)

            # Validate response structure
            if not all(k in result for k in ["label", "confidence"]):
                raise ValueError(
                    "Invalid response format: missing required fields"
                )

            # Validate label is in framework
            if result["label"] not in framework.labels:
                logger.warning(
                    f"LLM returned invalid label '{result['label']}', "
                    f"using first framework label"
                )
                result["label"] = framework.labels[0]

            # Validate confidence range
            confidence = float(result["confidence"])
            if not 0.0 <= confidence <= 1.0:
                logger.warning(
                    f"Invalid confidence {confidence}, clamping to [0,1]"
                )
                result["confidence"] = max(0.0, min(1.0, confidence))

            return result

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON response: {e}")
            raise ValueError(f"Invalid JSON in LLM response: {e}")
        except (APIConnectionError, RateLimitError, APIError) as e:
            logger.error(f"Analyzer API error: {type(e).__name__}: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Classification failed: {e}")
            raise

    async def batch_classify(
        self,
        questions: list[str],
        framework: AnalysisFramework,
        context: Optional[str] = None,
    ) -> list[Dict[str, any]]:
        """
        Classify multiple questions sequentially.

        Args:
            questions: List of teacher questions
            framework: Analysis framework
            context: Optional shared context

        Returns:
            List of classification results
        """
        results = []
        for question in questions:
            try:
                result = await self.classify_question(
                    question, framework, context
                )
                results.append(result)
            except Exception as e:
                logger.error(f"Failed to classify question '{question}': {e}")
                # Return default classification on failure
                results.append(
                    {
                        "label": framework.labels[0],
                        "confidence": 0.0,
                        "reasoning": f"Classification failed: {str(e)}",
                    }
                )
        return results
