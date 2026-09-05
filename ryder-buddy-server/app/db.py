"""数据库连接与表模型（SQLAlchemy 2.0 async）。"""
from datetime import datetime, timezone

from sqlalchemy import JSON, ForeignKey, String, Text, func
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from .config import get_settings

settings = get_settings()

_is_sqlite = settings.database_url.startswith("sqlite")

engine = create_async_engine(
    settings.database_url,
    echo=False,
    # SQLite：等待锁 30 秒 + WAL，避免家用演示时的 database is locked；
    # 生产用 Postgres（MVCC）无此问题
    connect_args={"timeout": 30} if _is_sqlite else {},
)
SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Family(Base):
    """一个家庭（当前只有一个女儿，child 信息放 profile JSON 里）"""

    __tablename__ = "families"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(64), default="我的家")
    # 记忆档案 + 莱德人设（父亲可随时改，全家共享）
    profile: Mapped[dict] = mapped_column(JSON, default=dict)
    persona: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())


class Member(Base):
    """家庭成员：father=管理员，member=普通成员（阿婆/妈妈/…）"""

    __tablename__ = "members"
    id: Mapped[int] = mapped_column(primary_key=True)
    family_id: Mapped[int] = mapped_column(ForeignKey("families.id"))
    role: Mapped[str] = mapped_column(String(16), default="member")  # father / member
    display_name: Mapped[str] = mapped_column(String(32), default="家人")
    username: Mapped[str] = mapped_column(String(64), unique=True)
    password_hash: Mapped[str] = mapped_column(String(128))
    invite_code: Mapped[str | None] = mapped_column(String(16), nullable=True)  # 生成的邀请码
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())


class ProviderKey(Base):
    """API Key 保险箱：只写不读（GET 永远只返回掩码），换 Key 即时生效"""

    __tablename__ = "provider_keys"
    id: Mapped[int] = mapped_column(primary_key=True)
    family_id: Mapped[int] = mapped_column(ForeignKey("families.id"))
    provider: Mapped[str] = mapped_column(String(32))  # llm / tts / asr
    base_url: Mapped[str] = mapped_column(String(256), default="")
    model: Mapped[str] = mapped_column(String(64), default="")
    api_key: Mapped[str] = mapped_column(String(256))
    voice: Mapped[str] = mapped_column(String(128), default="")  # TTS 音色（克隆音色 URI / 预设音色名）
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=utcnow)


class ChatLog(Base):
    """对话记录：按 member 区分是谁陪聊的，父亲可回放"""

    __tablename__ = "chat_logs"
    id: Mapped[int] = mapped_column(primary_key=True)
    family_id: Mapped[int] = mapped_column(ForeignKey("families.id"))
    member_id: Mapped[int] = mapped_column(ForeignKey("members.id"))
    member_name: Mapped[str] = mapped_column(String(32), default="")
    user_text: Mapped[str] = mapped_column(Text)
    reply_text: Mapped[str] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String(16), default="text")  # text / audio
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
