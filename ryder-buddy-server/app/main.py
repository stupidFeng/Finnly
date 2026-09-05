"""应用入口：建表、引导父亲账号、挂载路由。"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .auth import hash_password
from .config import get_settings
from .db import Base, Family, Member, engine, SessionLocal
from .routes import auth_routes, chat_routes, family_routes, history_routes

logging.basicConfig(level=logging.INFO)
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 建表（家用规模足够；后续要迁移再上 Alembic）
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        if settings.database_url.startswith("sqlite"):
            from sqlalchemy import text

            await conn.execute(text("PRAGMA journal_mode=WAL"))

    # 引导：保证至少有一个家庭 + 父亲管理员账号
    async with SessionLocal() as session:
        from sqlalchemy import func, select

        count = (await session.execute(select(func.count()).select_from(Member))).scalar_one()
        if count == 0:
            family = Family(name="我的家")
            session.add(family)
            await session.flush()
            session.add(Member(
                family_id=family.id,
                role="father",
                display_name="爸爸",
                username=settings.father_username,
                password_hash=hash_password(settings.father_password),
            ))
            await session.commit()
            logging.info(
                "已创建管理员账号 %s（首次登录后请尽快在 .env 改掉默认密码并重启）",
                settings.father_username,
            )
    yield
    await engine.dispose()


app = FastAPI(title="RyderBuddy 家庭后端", lifespan=lifespan)

# App 直连后端（Android WebView / 调试网页都要跨域），家用规模直接全放行
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_routes.router)
app.include_router(family_routes.router)
app.include_router(history_routes.router)
app.include_router(chat_routes.router)


@app.get("/health")
async def health():
    return {"ok": True}
