"""家庭管理路由：记忆档案 / 莱德人设 / API Key 保险箱 / 成员列表。"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth import get_current_member, require_father
from ..db import Family, Member, ProviderKey, SessionLocal
from ..schemas import (
    MemberBrief,
    MemoryProfile,
    PersonaConfig,
    ProviderKeyMasked,
    ProviderKeyRequest,
)

router = APIRouter(prefix="/family", tags=["family"])


async def get_family(session: AsyncSession, family_id: int) -> Family:
    family = await session.get(Family, family_id)
    if family is None:
        raise HTTPException(404, "家庭不存在")
    return family


# ---------- 记忆档案：全家可读（App 拉快照），仅父亲可写 ----------
@router.get("/profile", response_model=MemoryProfile)
async def get_profile(member: Member = Depends(get_current_member)):
    async with SessionLocal() as session:
        family = await get_family(session, member.family_id)
        return MemoryProfile(**(family.profile or {}))


@router.put("/profile", response_model=MemoryProfile)
async def put_profile(
    profile: MemoryProfile,
    member: Member = Depends(require_father),
):
    async with SessionLocal() as session:
        family = await get_family(session, member.family_id)
        family.profile = profile.model_dump()
        await session.commit()
        return profile


# ---------- 莱德人设：全家可读，仅父亲可写 ----------
@router.get("/persona", response_model=PersonaConfig)
async def get_persona(member: Member = Depends(get_current_member)):
    async with SessionLocal() as session:
        family = await get_family(session, member.family_id)
        return PersonaConfig(**(family.persona or {}))


@router.put("/persona", response_model=PersonaConfig)
async def put_persona(
    persona: PersonaConfig,
    member: Member = Depends(require_father),
):
    async with SessionLocal() as session:
        family = await get_family(session, member.family_id)
        family.persona = persona.model_dump()
        await session.commit()
        return persona


# ---------- API Key 保险箱：仅父亲可写；读永远只给掩码 ----------
@router.put("/keys")
async def put_key(
    req: ProviderKeyRequest,
    member: Member = Depends(require_father),
):
    """写入/更新某厂商配置。换 Key 即时生效，全家下次对话就用新的。"""
    async with SessionLocal() as session:
        existing = (await session.execute(
            select(ProviderKey).where(
                ProviderKey.family_id == member.family_id,
                ProviderKey.provider == req.provider,
            )
        )).scalar_one_or_none()
        if existing is None:
            existing = ProviderKey(family_id=member.family_id, provider=req.provider)
            session.add(existing)
        existing.base_url = req.base_url
        existing.model = req.model
        existing.voice = req.voice
        # api_key 留空表示"只改地址/模型，不换 Key"——App 端从不回传真实 Key
        if req.api_key:
            existing.api_key = req.api_key
        await session.commit()


@router.get("/keys", response_model=list[ProviderKeyMasked])
async def list_keys(member: Member = Depends(require_father)):
    async with SessionLocal() as session:
        rows = (await session.execute(
            select(ProviderKey).where(ProviderKey.family_id == member.family_id)
        )).scalars().all()
        return [
            ProviderKeyMasked(
                provider=r.provider,
                base_url=r.base_url,
                model=r.model,
                api_key_masked=mask(r.api_key),
                voice=r.voice,
                updated_at=r.updated_at,
            )
            for r in rows
        ]


def mask(key: str) -> str:
    if not key:
        return ""
    if len(key) <= 8:
        return "****"
    return key[:4] + "****" + key[-4:]


# ---------- 成员：全家可看名单（App 上显示“阿婆的手机”等），仅父亲可删 ----------
@router.get("/members", response_model=list[MemberBrief])
async def list_members(member: Member = Depends(get_current_member)):
    async with SessionLocal() as session:
        rows = (await session.execute(
            select(Member).where(Member.family_id == member.family_id)
        )).scalars().all()
        return [
            MemberBrief(id=r.id, display_name=r.display_name, role=r.role) for r in rows
        ]
