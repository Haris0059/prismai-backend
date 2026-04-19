from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    database_url: str
    database_url_direct: str | None = None
    anthropic_api_key: str | None = None
    openai_api_key: str | None = None
    gemini_api_key: str | None = None
    firebase_project_id: str | None = None
    firebase_service_account_path: str | None = None
    dev_auth_bypass: bool = False

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings()
