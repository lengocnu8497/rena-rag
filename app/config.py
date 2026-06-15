from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False, extra="ignore")

    # Anthropic
    anthropic_api_key: str

    # OpenAI (embeddings only)
    openai_api_key: str

    # Supabase — service role for all DB/vector ops
    supabase_url: str
    supabase_service_role_key: str

    # AWS
    aws_region: str = "us-east-1"

    # Runtime
    environment: str = "development"
    log_level: str = "INFO"


settings = Settings()  # type: ignore[call-arg]
