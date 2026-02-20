from functools import lru_cache
from pathlib import Path

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
    chessdojo_cognito_region: str = Field(default="us-east-1")
    chessdojo_cognito_user_pool_client_id: str = Field(
        default="1dfi5rar7a2fr5samugigrmise"
    )
    chessdojo_cognito_auth_domain: str = Field(default="auth.chessdojo.club")
    chessdojo_oauth_redirect_uri: str = Field(default="https://www.chessdojo.club")
    chessdojo_oauth_scope: str = Field(default="openid email profile")
    auth_refresh_skew_seconds: int = Field(default=120)
    local_auth_state_path: str = Field(default="")

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

    def normalized_token_value(self, raw_value: str) -> str:
        token = raw_value.strip()
        if (
            (token.startswith('"') and token.endswith('"'))
            or (token.startswith("'") and token.endswith("'"))
        ):
            token = token[1:-1].strip()
        if token.lower().startswith("bearer "):
            token = token[7:].strip()
        return token

    def cognito_idp_url(self) -> str:
        return f"https://cognito-idp.{self.chessdojo_cognito_region}.amazonaws.com/"

    def cognito_oauth_authorize_url(self) -> str:
        domain = self.chessdojo_cognito_auth_domain.strip()
        if domain.startswith("https://"):
            domain = domain[8:]
        elif domain.startswith("http://"):
            domain = domain[7:]
        domain = domain.strip("/")
        return f"https://{domain}/oauth2/authorize"

    def cognito_oauth_token_url(self) -> str:
        domain = self.chessdojo_cognito_auth_domain.strip()
        if domain.startswith("https://"):
            domain = domain[8:]
        elif domain.startswith("http://"):
            domain = domain[7:]
        domain = domain.strip("/")
        return f"https://{domain}/oauth2/token"

    def resolved_auth_state_path(self) -> Path:
        raw_path = self.local_auth_state_path.strip()
        if raw_path:
            return Path(raw_path).expanduser()
        return Path.home() / ".dojotap" / "auth_state.json"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
