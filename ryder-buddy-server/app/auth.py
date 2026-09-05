"""JWT 鉴权：父亲（管理员）/ 普通成员（家人）两种角色。"""
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .config import get_settings
from .db import Member, SessionLocal

settings = get_settings()
bearer = HTTPBearer(auto_error=False)


def hash_password(raw: str) -> str:
    # bcrypt 只取前 72 字节，家庭场景密码不会超
    return bcrypt.hashpw(raw.encode()[:72], bcrypt.gensalt()).decode()


def verify_password(raw: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(raw.encode()[:72], hashed.encode())
    except ValueError:
        return False


def create_token(member: Member) -> str:
    payload = {
        "sub": str(member.id),
        "family_id": member.family_id,
        "role": member.role,
        "name": member.display_name,
        "exp": datetime.now(timezone.utc) + timedelta(days=settings.jwt_expire_days),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")


async def get_current_member(
    creds: HTTPAuthorizationCredentials | None = Depends(bearer),
) -> Member:
    if creds is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "未登录")
    try:
        payload = jwt.decode(creds.credentials, settings.jwt_secret, algorithms=["HS256"])
    except jwt.PyJWTError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "登录已过期，请重新登录")

    async with SessionLocal() as session:
        member = await session.get(Member, int(payload["sub"]))
        if member is None:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "账号不存在")
        return member


async def require_father(member: Member = Depends(get_current_member)) -> Member:
    if member.role != "father":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "只有父亲（管理员）可以操作")
    return member


def decode_token(token: str) -> dict:
    return jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
