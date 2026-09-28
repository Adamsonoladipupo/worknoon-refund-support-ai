from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str

    app_env: str = "development"
    app_debug: bool = False

    # Optional at load time so the app can start without it; AIService raises
    # AIServiceConfigError at call time if it is absent.
    ai_api_key: str | None = None
    ai_model: str = "gemini-2.0-flash"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )


settings = Settings()  # type: ignore[call-arg]
