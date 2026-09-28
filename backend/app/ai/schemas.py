"""
AI layer data contracts.

These types define what the AI service receives and returns.  They are
intentionally independent of app.policies.refund_policy — the two packages
use the same enum values (DAMAGED_ITEM / INCORRECT_ITEM / OTHER) but belong
to separate bounded contexts:

  app.policies  — deterministic, authoritative refund decisions
  app.ai        — probabilistic extraction from free-text customer messages

The caller (future service orchestrator) is responsible for mapping an
ai.RefundReason to a policy.RefundReason when bridging the two layers.
"""

from __future__ import annotations

from decimal import Decimal
from enum import Enum

from pydantic import BaseModel, field_validator


class RefundReason(str, Enum):
    """
    Possible refund reasons the AI can extract from a customer message.

    Mirrors app.policies.refund_policy.RefundReason intentionally; kept
    separate so the AI layer has zero import dependency on the policy layer.
    """

    DAMAGED_ITEM = "DAMAGED_ITEM"
    INCORRECT_ITEM = "INCORRECT_ITEM"
    OTHER = "OTHER"


class RefundRequestAnalysis(BaseModel):
    """
    Structured output produced by AIService.analyze_request().

    This is the contract between the AI layer and the rest of the application.
    Changing this model is a breaking change — update tests and callers.

    Fields
    ------
    reason
        The refund reason extracted from the customer's message.
    summary
        A concise, factual restatement of the customer's request in neutral
        language.  Must not contain any claim about approval/denial/escalation.
    requested_amount
        The monetary amount explicitly stated by the customer, or None if no
        amount was mentioned.  Never invented by the AI.  Decimal, never float.
    confidence
        How confident the AI is in the extracted reason, on a [0, 1] scale.
        A value of 1.0 means the AI is certain; 0.0 means it cannot tell.
    """

    reason: RefundReason
    summary: str
    requested_amount: Decimal | None = None
    confidence: Decimal

    @field_validator("confidence")
    @classmethod
    def confidence_must_be_between_0_and_1(cls, v: Decimal) -> Decimal:
        if v < Decimal("0") or v > Decimal("1"):
            raise ValueError(
                f"confidence must be between 0 and 1 inclusive, got {v}"
            )
        return v

    @field_validator("requested_amount")
    @classmethod
    def requested_amount_must_not_be_float_zero(cls, v: Decimal | None) -> Decimal | None:
        # Guard: reject explicit zero — an amount of 0 is meaningless and
        # likely a parsing artefact rather than a real request.
        if v is not None and v <= Decimal("0"):
            raise ValueError(
                "requested_amount must be greater than zero if provided"
            )
        return v

    model_config = {"frozen": True}
