"""
AI analysis package.

Analyses free-text customer refund messages using Google Gemini.
Independent of SQLAlchemy, FastAPI, RefundPolicy, and RefundService.
"""

from app.ai.schemas import RefundReason, RefundRequestAnalysis
from app.ai.service import AIService

__all__ = [
    "RefundReason",
    "RefundRequestAnalysis",
    "AIService",
]
