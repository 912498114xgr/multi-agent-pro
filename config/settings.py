from functools import lru_cache
from pathlib import Path
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """集中配置，从 .env 与环境变量加载。"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # API
    api_key: str = "dev-api-key"
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"

    # LLM（与现有 .env 字段名对齐）
    openai_base_url: str = "https://api.openai.com/v1"
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"

    # 外部服务
    tavily_api_key: str = ""
    mysql_host: str = "localhost"
    mysql_port: int = 3306
    mysql_user: str = ""
    mysql_password: str = ""
    mysql_database: str = "xiaoneng_db"
    mysql_charset: str = "utf8mb4"
    mysql_collation: str = "utf8mb4_unicode_ci"
    mysql_sql_mode: str = "TRADITIONAL"
    ragflow_api_url: str = ""
    ragflow_api_key: str = ""

    # 限制
    max_upload_mb: int = 20
    task_timeout_sec: int = 600
    prompt_version: str = "v1"

    # 路径
    project_root: Path = Path(__file__).resolve().parents[1]
    output_dir_name: str = "output"
    upload_dir_name: str = "updated"

    @property
    def output_dir(self) -> Path:
        return self.project_root / self.output_dir_name

    @property
    def upload_dir(self) -> Path:
        return self.project_root / self.upload_dir_name

    @property
    def cors_origin_list(self) -> List[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024

    def mysql_config(self) -> dict:
        config = {
            "host": self.mysql_host,
            "port": self.mysql_port,
            "user": self.mysql_user,
            "password": self.mysql_password,
            "database": self.mysql_database,
            "charset": self.mysql_charset,
            "collation": self.mysql_collation,
            "autocommit": True,
            "sql_mode": self.mysql_sql_mode,
        }
        return {k: v for k, v in config.items() if v is not None and v != ""}


@lru_cache
def get_settings() -> Settings:
    return Settings()
