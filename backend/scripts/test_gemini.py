#!/usr/bin/env python
"""
Manual integration test for the Gemini AI boundary.

This script is NOT part of the automated pytest suite.
Run it locally to verify that your real Gemini API key and model are working.

Usage
─────
    cd backend
    python scripts/test_gemini.py

Requirements
────────────
- AI_API_KEY must be set in your environment or in a .env file.
- AI_MODEL may optionally be set (defaults to gemini-2.0-flash).

The script will:
  1. Load settings and verify AI_API_KEY is present (without printing it).
  2. Instantiate AIService.
  3. Send one safe refund-related message to Gemini.
  4. Print the structured RefundRequestAnalysis result.
  5. Exit 0 on success, 1 on any failure.

The API key is NEVER printed.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

# Ensure the backend package root is on sys.path when run as a script.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.ai.exceptions import AIServiceConfigError, AIServiceError
from app.ai.service import AIService
from app.core.config import settings

# A safe, realistic test message — contains no sensitive data.
_TEST_MESSAGE = (
    "Hi, I received my order yesterday but the item arrived with a cracked "
    "screen. I paid $49.99 for it and would like a full refund please."
)


async def _run() -> None:
    print("=== Worknoon Gemini Integration Test ===\n")

    if not settings.ai_api_key:
        print(
            "ERROR: AI_API_KEY is not set.\n"
            "Set it in your environment or in a .env file:\n"
            "  AI_API_KEY=<your-gemini-api-key>\n"
            "\nObtain a key from https://aistudio.google.com/app/apikey"
        )
        sys.exit(1)

    key_preview = settings.ai_api_key[:8] + "..." if len(settings.ai_api_key) > 8 else "***"
    print(f"AI_API_KEY : {key_preview}  (not printed in full)")
    print(f"AI_MODEL   : {settings.ai_model}")
    print()

    try:
        service = AIService()
    except AIServiceConfigError as exc:
        print(f"Configuration error: {exc}")
        sys.exit(1)

    print("Test message:")
    print(f"  {_TEST_MESSAGE!r}")
    print()
    print("Calling Gemini API… ", end="", flush=True)

    try:
        analysis = await service.analyze_request(_TEST_MESSAGE)
    except AIServiceConfigError as exc:
        print("FAILED")
        print(f"\nConfiguration error: {exc}")
        sys.exit(1)
    except AIServiceError as exc:
        print("FAILED")
        print(f"\nAI service error: {exc}")
        sys.exit(1)
    except Exception as exc:
        print("FAILED")
        print(f"\nUnexpected error ({type(exc).__name__}): {exc}")
        sys.exit(1)

    print("OK\n")

    print("RefundRequestAnalysis:")
    print(f"  reason           : {analysis.reason.value}")
    print(f"  summary          : {analysis.summary}")
    print(f"  requested_amount : {analysis.requested_amount}")
    print(f"  confidence       : {analysis.confidence}")
    print()
    print("SUCCESS — Gemini integration is working correctly.")


if __name__ == "__main__":
    asyncio.run(_run())
