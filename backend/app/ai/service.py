"""
AI service — Google Gemini implementation (Phase 8B).

Public interface
────────────────
    service = AIService()
    analysis = await service.analyze_request(msg)  # → RefundRequestAnalysis

Structured output
─────────────────
We pass response_mime_type="application/json" and response_schema=_LLMOutput
to GenerateContentConfig.  Gemini constrains its output to a JSON object that
matches the schema, which Pydantic then validates.

The system instruction (SYSTEM_PROMPT) is passed via GenerateContentConfig,
keeping it strictly separate from the customer message.  The customer message
is the sole content of the user turn — it is never embedded inside the system
instruction.  This is the structural defence against prompt-injection.

Decimal handling
────────────────
Gemini's JSON schema cannot express Decimal.  _LLMOutput uses str | None for
requested_amount and float for confidence.  _to_analysis() converts both to
Decimal before constructing the public RefundRequestAnalysis.

Error handling
──────────────
Missing API key        → AIServiceConfigError (raised at construction)
Gemini API / network   → AIServiceError (wraps original; key never exposed)
Malformed JSON         → AIServiceError
Pydantic validation    → AIServiceError
Empty response         → AIServiceError

Independence
────────────
No dependency on SQLAlchemy, FastAPI, RefundPolicy, or RefundService.
"""

from __future__ import annotations

import json
from decimal import Decimal, InvalidOperation
from typing import Annotated

import google.genai as genai
import google.genai.errors as genai_errors
import google.genai.types as genai_types
from pydantic import BaseModel, Field, ValidationError, field_validator

from app.ai.exceptions import AIServiceConfigError, AIServiceError
from app.ai.prompts import SYSTEM_PROMPT
from app.ai.schemas import RefundReason, RefundRequestAnalysis
from app.core.config import settings


# ---------------------------------------------------------------------------
# Internal model — JSON-native types for Gemini structured output
# ---------------------------------------------------------------------------


class _LLMOutput(BaseModel):
    """
    Intermediate Pydantic model used as response_schema for the Gemini call.

    Uses JSON-native types (str, float) because Gemini's JSON schema generator
    does not support Decimal.  Values are converted to the public
    RefundRequestAnalysis (Decimal) in _to_analysis() after validation.

    Private to this module — callers never see it.
    """

    reason: RefundReason
    summary: str
    requested_amount: str | None = None
    confidence: Annotated[float, Field(ge=0.0, le=1.0)]

    @field_validator("requested_amount")
    @classmethod
    def _clean_amount(cls, v: str | None) -> str | None:
        """Strip currency symbols; reject non-numeric or non-positive strings."""
        if v is None:
            return None
        cleaned = v.strip().lstrip("$£€").strip()
        if not cleaned:
            return None
        try:
            val = Decimal(cleaned)
        except InvalidOperation:
            return None
        if val <= Decimal("0"):
            return None
        return cleaned


# ---------------------------------------------------------------------------
# AIService
# ---------------------------------------------------------------------------


class AIService:
    """
    Analyses a free-text customer refund message using Google Gemini.

    Raises AIServiceConfigError at construction if AI_API_KEY is absent —
    misconfiguration surfaces immediately rather than mid-request.

    Usage::

        service = AIService()
        analysis = await service.analyze_request(
            "My item arrived with a cracked screen."
        )
        # analysis.reason     → RefundReason.DAMAGED_ITEM
        # analysis.confidence → Decimal("0.95")

    The public interface (analyze_request signature + return type) is stable.
    """

    def __init__(self) -> None:
        if not settings.ai_api_key:
            raise AIServiceConfigError(
                "AI_API_KEY is not configured. "
                "Set the AI_API_KEY environment variable to use AIService. "
                "Obtain a key from https://aistudio.google.com/app/apikey"
            )
        self._client = genai.Client(api_key=settings.ai_api_key)
        self._model = settings.ai_model

    async def analyze_request(self, message: str) -> RefundRequestAnalysis:
        """
        Analyse a customer refund message and return structured output.

        The system instruction contains our trusted rules.
        The customer message is passed separately as user content — it is
        NEVER embedded inside the system instruction.  This structural
        separation is the primary defence against prompt-injection.

        Parameters
        ----------
        message:
            Raw free-text from the customer.  Untrusted; never mixed into the
            system instruction.

        Returns
        -------
        RefundRequestAnalysis
            Structured extraction result.  Must not be used to make a refund
            decision — that is the sole responsibility of RefundPolicy.

        Raises
        ------
        AIServiceConfigError
            If the API key is absent (raised at construction).
        AIServiceError
            On Gemini API error, network failure, empty response, or output
            that fails schema validation.
        """
        config = genai_types.GenerateContentConfig(
            # System instruction — trusted; set here, never in user content.
            system_instruction=SYSTEM_PROMPT,
            # Constrain output to a JSON object matching our schema.
            response_mime_type="application/json",
            response_schema=_LLMOutput,
            # Low temperature for deterministic extraction tasks.
            temperature=0.0,
        )

        try:
            response = await self._client.aio.models.generate_content(
                model=self._model,
                # Customer message as user content — untrusted data.
                contents=message,
                config=config,
            )
        except genai_errors.APIError as exc:
            # Do NOT propagate exc.message — it can contain internal API details,
            # quota information, or other provider-specific data that must not
            # be surfaced to the caller or HTTP response body.
            raise AIServiceError(
                f"The AI analysis service is temporarily unavailable "
                f"({type(exc).__name__}). Please try again later."
            ) from exc
        except Exception as exc:
            raise AIServiceError(
                f"Unexpected error calling the AI analysis service: {type(exc).__name__}"
            ) from exc

        # Extract the raw JSON text from the response.
        raw_text: str | None = None
        try:
            raw_text = response.text
        except Exception:
            pass

        if not raw_text or not raw_text.strip():
            raise AIServiceError(
                "Gemini returned an empty response. "
                "The model may have triggered a safety filter."
            )

        # Parse and validate through the internal model.
        try:
            llm_output = _LLMOutput.model_validate_json(raw_text)
        except (ValidationError, json.JSONDecodeError, ValueError) as exc:
            raise AIServiceError(
                f"Gemini returned output that failed schema validation: {exc}"
            ) from exc

        return _to_analysis(llm_output)


# ---------------------------------------------------------------------------
# Conversion helper
# ---------------------------------------------------------------------------


def _to_analysis(llm: _LLMOutput) -> RefundRequestAnalysis:
    """Convert the internal _LLMOutput to the public RefundRequestAnalysis."""
    requested_amount: Decimal | None = None
    if llm.requested_amount is not None:
        try:
            requested_amount = Decimal(llm.requested_amount)
        except InvalidOperation:
            requested_amount = None

    # Round to 4 decimal places to eliminate floating-point representation noise.
    confidence = Decimal(str(round(llm.confidence, 4)))

    return RefundRequestAnalysis(
        reason=llm.reason,
        summary=llm.summary,
        requested_amount=requested_amount,
        confidence=confidence,
    )
