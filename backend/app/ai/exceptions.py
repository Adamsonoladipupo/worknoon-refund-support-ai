"""
Exceptions raised by the AI analysis layer.

Kept in a dedicated module so callers can import them without pulling in the
service implementation (which imports the OpenAI SDK).
"""


class AIServiceError(Exception):
    """Base class for all errors raised by AIService.

    Catch this to handle any AI-layer failure without caring about the
    specific cause.
    """


class AIServiceConfigError(AIServiceError):
    """Raised when AIService cannot be used due to a configuration problem.

    Typical cause: AI_API_KEY environment variable is not set.
    """
