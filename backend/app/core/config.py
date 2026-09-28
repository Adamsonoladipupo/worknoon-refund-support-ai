from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Database
    database_url: str

    # Application
    app_env: str = "development"
    app_debug: bool = False

    # AI / LLM
    # ai_api_key is optional at settings-load time so the app can start without
    # it; AIService raises AIServiceConfigError at call time if it is absent.
    ai_api_key: str | None = None
    # gemini-2.0-flash supports structured output and is the recommended default.
    # Override via AI_MODEL env var (e.g. gemini-1.5-pro for higher accuracy).
    ai_model: str = "gemini-2.0-flash"

    model_config = SettingsConfigDict(
        # Load from .env file if present; never required in production
        # (real env vars always take precedence over the file).
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )


# Single shared instance — import this everywhere instead of re-instantiating.
settings = Settings()  # type: ignore[call-arg]
