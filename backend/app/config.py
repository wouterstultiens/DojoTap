from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    chessdojo_base_url: str = Field(
        default="https://g4shdaq6ug.execute-api.us-east-1.amazonaws.com"
    )
    chessdojo_bearer_token: str = Field(default="")
    request_timeout_seconds: float = Field(default=20.0)
    allow_origin: str = Field(default="http://localhost:5173")

    def normalized_bearer_token(self) -> str:
        token = self.chessdojo_bearer_token.strip()
        if (
            (token.startswith('"') and token.endswith('"'))
            or (token.startswith("'") and token.endswith("'"))
        ):
            token = token[1:-1].strip()
        if token.lower().startswith("bearer "):
            token = token[7:].strip()
        return token


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
