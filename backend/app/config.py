from pydantic_settings import BaseSettings
from functools import lru_cache
import os
from pathlib import Path


class Settings(BaseSettings):
    # Server
    host: str = "0.0.0.0"
    port: int = 8863
    cors_origins: str = "http://localhost:5173,http://localhost:8863,http://192.168.*:5173,http://192.168.*:5174,http://localhost:8864,http://localhost:8863"
    debug: bool = False

    # Authentication
    vibe2crazy_password: str = "password"
    session_expire_hours: int = 24
    secret_key: str = "change-this-secret-key"

    # Storage
    projects_dir: str = "./projects"
    database_url: str = "sqlite:///./data/vibe2crazy.db"

    # Git
    git_default_branch: str = "main"

    # Tmux
    tmux_session_prefix: str = "vibe2crazy-"

    # Tunnel
    tunnel_server_url: str = "https://vibe2crazy.com"
    tunnel_default_tls: bool = True
    tunnel_verify_tls: bool = False

    # Update check
    update_server_url: str = ""  # vibe2crazy_server URL for update checks
    current_version: str = "1.0.0"  # Current vibe2crazy version

    # Rate limiting
    rate_limit_enabled: bool = True
    rate_limit_auth: str = "5/minute"
    rate_limit_default: str = "100/minute"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

    @property
    def cors_origin_regex(self) -> str:
        """
        正则表达式匹配所有允许的 CORS 来源:
        - localhost 和 127.0.0.1 (所有端口)
        - frp-oil.com 和 vibe2crazy.com 及其子域名 (所有端口)
        - 三种私有 IP 网段 (所有端口):
          - 10.0.0.0/8
          - 172.16.0.0/12
          - 192.168.0.0/16
        """
        return (
            r"^(https?://)?("
            r"localhost|"
            r"127\.0\.0\.1|"
            r"([a-zA-Z0-9-]+\.)*(frp-oil\.com|vibe2crazy\.com)|"
            r"10\.\d{1,3}\.\d{1,3}\.\d{1,3}|"
            r"172\.(1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3}|"
            r"192\.168\.\d{1,3}\.\d{1,3}"
            r")(:\d+)?$"
        )

    @property
    def projects_path(self) -> Path:
        # Resolve to absolute path to avoid issues with file operations
        path = Path(self.projects_dir).resolve()
        path.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def database_path(self) -> Path:
        path = Path(self.database_url.replace("sqlite:///", ""))
        path.parent.mkdir(parents=True, exist_ok=True)
        return path


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
