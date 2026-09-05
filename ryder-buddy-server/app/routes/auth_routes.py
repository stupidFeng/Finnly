"""鉴权路由：登录（成员）/ 加入家庭（邀请码）。"""
import secrets

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth import create_token, get_current_member, hash_password, require_father, verify_password
from ..db import Family, Member, SessionLocal
from ..schemas import InviteResponse, JoinRequest, LoginRequest, NewMemberRequest, TokenResponse

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
async def login(req: LoginRequest):
    async with SessionLocal() as session:
        member = (await session.execute(
            select(Member).where(Member.username == req.username)
        )).scalar_one_or_none()
        if member is None or not verify_password(req.password, member.password_hash):
            raise HTTPException(401, "用户名或密码不对")
        return TokenResponse(
            token=create_token(member),
            role=member.role,
            display_name=member.display_name,
        )


@router.post("/join", response_model=TokenResponse)
async def join_by_invite(req: JoinRequest):
    """家人拿父亲发的邀请码自助注册，无需父亲代填密码。"""
    async with SessionLocal() as session:
        inviter = (await session.execute(
            select(Member).where(Member.invite_code == req.invite_code)
        )).scalar_one_or_none()
        if inviter is None:
            raise HTTPException(404, "邀请码不对或已过期")
        # 用邀请码生成一个随机账号（家人不需要记密码，凭设备上的 token 用）
        username = f"member_{secrets.token_hex(4)}"
        member = Member(
            family_id=inviter.family_id,
            role="member",
            display_name=req.display_name,
            username=username,
            password_hash=hash_password(secrets.token_hex(8)),
        )
        session.add(member)
        await session.commit()
        await session.refresh(member)
        return TokenResponse(
            token=create_token(member),
            role=member.role,
            display_name=member.display_name,
        )


@router.post("/invite", response_model=InviteResponse)
async def create_invite(member: Member = Depends(require_father)):
    """父亲生成/刷新邀请码（旧码自动作废）。"""
    async with SessionLocal() as session:
        db_member = await session.get(Member, member.id)
        db_member.invite_code = secrets.token_hex(4)  # 8 位，够家用且好念
        await session.commit()
        return InviteResponse(invite_code=db_member.invite_code)


@router.get("/me", response_model=TokenResponse)
async def whoami(member: Member = Depends(get_current_member)):
    return TokenResponse(
        token="",  # /me 不重复发 token
        role=member.role,
        display_name=member.display_name,
    )
