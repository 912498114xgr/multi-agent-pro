"""
config/settings.py — 项目集中配置中心

职责：
  - 定义所有可配置项的类型、默认值
  - 从 .env 文件和环境变量自动加载（pydantic-settings）
  - 提供 get_settings() 单例，全项目统一读取配置

.env 字段映射规则（自动）：
  openai_model  ←  OPENAI_MODEL
  mysql_host    ←  MYSQL_HOST
  ...

使用示例：
  from config.settings import get_settings
  s = get_settings()
  s.mysql_config()   # 给 mysql.connector 用
  s.output_dir       # 报告输出目录 Path 对象
"""

from functools import lru_cache
from pathlib import Path
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict

_ENV_FILE = Path(__file__).resolve().parents[1] / ".env"


class Settings(BaseSettings):
    """
    应用配置类。继承 BaseSettings 后，字段名会自动映射为大写环境变量。
    extra="ignore" 表示 .env 里多写的变量不会报错。
    """

    model_config = SettingsConfigDict(
        env_file=str(_ENV_FILE),   # 固定读项目根目录 .env，不依赖启动 cwd
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ---------- API 层（Phase 5 使用）----------
    api_key: str = "dev-api-key"   # 请求头 X-API-Key 校验
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173,http://localhost:3000,http://127.0.0.1:3000"

    # ---------- LLM 大模型 ----------
    # 兼容 OpenAI 协议的中转（如 edgefn、dashscope compatible-mode）
    openai_base_url: str = "https://api.openai.com/v1"
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"   # .env 中对应 OPENAI_MODEL，如 GLM-5
    openai_timeout_sec: int = 120       # LLM HTTP 超时（秒）

    # ---------- 外部数据源 ----------
    tavily_api_key: str = ""            # 行业检索助手
    mysql_host: str = "localhost"
    mysql_port: int = 3306
    mysql_user: str = ""
    mysql_password: str = ""
    mysql_database: str = "xiaoneng_db"  # 研发效能库
    mysql_charset: str = "utf8mb4"
    mysql_collation: str = "utf8mb4_unicode_ci"
    mysql_sql_mode: str = "TRADITIONAL"
    ragflow_api_url: str = ""           # 规范知识助手（MVP 可留空）
    ragflow_api_key: str = ""

    # ---------- Redis（checkpoint + 任务状态持久化）----------
    redis_url: str = ""                 # 例: redis://localhost:6379/0；空则内存模式
    redis_checkpoint_ttl_sec: int = 86400  # checkpoint TTL（秒），0 表示不过期

    # ---------- 调试 ----------
    runner_debug: bool = False          # RUNNER_DEBUG=1 时打印 astream 全量 chunk

    # ---------- 业务限制 ----------
    max_upload_mb: int = 20             # 上传文件大小上限
    task_timeout_sec: int = 600         # 单任务最长执行秒数
    prompt_version: str = "v1"          # Prompt 版本号，写入 loader 元数据

    # ---------- 路径（相对项目根）----------
    project_root: Path = Path(__file__).resolve().parents[1]
    output_dir_name: str = "output"     # Agent 生成的报告存放处
    upload_dir_name: str = "updated"    # 用户上传文件暂存处

    @property
    def output_dir(self) -> Path:
        """会话报告目录的根：output/session_{thread_id}/"""
        return self.project_root / self.output_dir_name

    @property
    def upload_dir(self) -> Path:
        """用户上传目录的根：updated/session_{thread_id}/"""
        return self.project_root / self.upload_dir_name

    @property
    def cors_origin_list(self) -> List[str]:
        """把 cors_origins 字符串拆成列表，供 FastAPI CORSMiddleware 使用。"""
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def max_upload_bytes(self) -> int:
        """上传大小上限（字节），api/server 校验用。"""
        return self.max_upload_mb * 1024 * 1024

    @property
    def use_redis_task_store(self) -> bool:
        """配置 REDIS_URL 时任务状态写入 Redis，支持崩溃恢复。"""
        return bool(self.redis_url.strip())

    def mysql_config(self) -> dict:
        """
        组装 mysql.connector.connect() 所需参数字典。
        过滤掉空值，避免传入 None 导致连接异常。
        """
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
    """
    获取配置单例。lru_cache 保证全进程只实例化一次 Settings。
    注意：修改 .env 后需重启进程才能生效。
    """
    return Settings()
