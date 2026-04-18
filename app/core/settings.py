from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    database_url: str
    database_url_direct: str | None = None
    anthropic_api_key: str | None = None
    openai_api_key: str | None = None
    firebase_project_id: str | None = None

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings()
