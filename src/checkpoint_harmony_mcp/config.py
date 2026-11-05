from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    checkpoint_client_id: str
    checkpoint_secret: SecretStr
    checkpoint_auth_url: str
    checkpoint_api_url: str
    checkpoint_scope: str = ""
    checkpoint_timeout: int = 30
    log_level: str = "INFO"
    mcp_http_host: str = "127.0.0.1"
    mcp_http_port: int = 8765

    @field_validator("checkpoint_api_url", "checkpoint_auth_url")
    @classmethod
    def _strip_slash(cls, v: str) -> str:
        return v.rstrip("/")
