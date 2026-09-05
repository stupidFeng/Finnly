"""对话历史：落库 + 父亲回放。"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth import get_current_member, require_father
from ..db import ChatLog, SessionLocal
from ..schemas import ChatLogItem, ChatLogPage

router = APIRouter(prefix="/history", tags=["history"])


@router.get("", response_model=ChatLogPage)
async def list_history(
    member=Depends(require_father),  # 只有父亲能看全家记录
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
):
    async with SessionLocal() as session:
        base = select(ChatLog).where(ChatLog.family_id == member.family_id)
        total = (await session.execute(
            select(func.count()).select_from(base.subquery())
        )).scalar_one()
        rows = (await session.execute(
            base.order_by(ChatLog.id.desc()).limit(limit).offset(offset)
        )).scalars().all()
        return ChatLogPage(
            items=[
                ChatLogItem(
                    id=r.id,
                    member_name=r.member_name,
                    user_text=r.user_text,
                    reply_text=r.reply_text,
                    source=r.source,
                    created_at=r.created_at,
                )
                for r in rows
            ],
            total=total,
        )


async def save_log(
    family_id: int, member_id: int, member_name: str,
    user_text: str, reply_text: str, source: str,
):
    """每轮对话结束后落库（orchestrator 完成时调用）。"""
    async with SessionLocal() as session:
        session.add(ChatLog(
            family_id=family_id,
            member_id=member_id,
            member_name=member_name,
            user_text=user_text,
            reply_text=reply_text,
            source=source,
        ))
        await session.commit()


async def load_recent_history(session: AsyncSession, family_id: int, window: int) -> list[dict]:
    """取最近 N 轮对话作为 LLM 上下文（跨请求、跨设备共享）。"""
    rows = (await session.execute(
        select(ChatLog)
        .where(ChatLog.family_id == family_id)
        .order_by(ChatLog.id.desc())
        .limit(window)
    )).scalars().all()
    history: list[dict] = []
    for r in reversed(rows):  # 时间正序
        history.append({"role": "user", "content": r.user_text})
        history.append({"role": "assistant", "content": r.reply_text})
    return history
