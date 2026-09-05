"""全局配置：全部来自环境变量 / .env 文件，敏感项绝不写死。"""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # 数据库：默认本地开发用 SQLite；docker-compose 里通过环境变量切 Postgres
    database_url: str = "sqlite+aiosqlite:///./ryder.db"

    # JWT 密钥：部署时必须改成强随机串（openssl rand -hex 32）
    jwt_secret: str = "CHANGE_ME_IN_PRODUCTION"
    jwt_expire_days: int = 30

    # 父亲（管理员）引导账号：首次启动自动创建
    father_username: str = "papa"
    father_password: str = "ryder2026"

    # SSE 心跳间隔（秒）
    heartbeat_seconds: float = 15.0

    # 对话历史保留条数（发给 LLM 的上下文窗口）
    llm_history_window: int = 12


@lru_cache
def get_settings() -> Settings:
    return Settings()
