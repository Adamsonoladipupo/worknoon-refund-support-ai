"""
AI analysis package.

This package defines the contract between the application and a language model.
It is intentionally independent of SQLAlchemy, FastAPI, RefundPolicy, and
RefundService — it only deals with analysing free-text customer messages.

Current state: mock/stub implementation (Phase 8A).
Future state: the mock in service.py will be replaced with a real LLM call
(Phase 8B+) without any changes to the public interface.
"""

from app.ai.schemas import RefundReason, RefundRequestAnalysis
from app.ai.service import AIService

__all__ = [
    "RefundReason",
    "RefundRequestAnalysis",
    "AIService",
]
