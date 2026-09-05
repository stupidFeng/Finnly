"""SSE 对话端点。

/chat/text  —— 主路径：App 本地 ASR 完，上传文本（省流量）
/chat/audio —— 兜底路径：App 上传音频，云端再识别一遍（孩子说不清时用）

两个端点共用编排器与事件协议，见 app/orchestrator.py。
"""
import asyncio
import json

from fastapi import APIRouter, Depends, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..asr import AsrError, transcribe
from ..auth import get_current_member
from ..config import get_settings
from ..db import ChatLog, Family, Member, ProviderKey, SessionLocal
from ..orchestrator import Orchestrator, done_event, error_event, heartbeat_loop, sse
from ..schemas import ChatTextRequest
from .history_routes import load_recent_history, save_log

router = APIRouter(prefix="/chat", tags=["chat"])
settings = get_settings()


async def _load_context(member: Member, user_text: str) -> tuple[dict, dict, dict, dict, list[dict]]:
    """一次性取出：记忆档案、人设、LLM/TTS 配置、最近对话上下文。"""
    async with SessionLocal() as session:
        family = await session.get(Family, member.family_id)
        keys = (await session.execute(
            select(ProviderKey).where(ProviderKey.family_id == member.family_id)
        )).scalars().all()
        by_provider = {k.provider: k for k in keys}
        history = await load_recent_history(
            session, member.family_id, settings.llm_history_window // 2
        )
    history.append({"role": "user", "content": user_text})
    return (
        family.profile or {},
        family.persona or {},
        cfg_dict(by_provider.get("llm")),
        cfg_dict(by_provider.get("tts")),
        history,
    )


def cfg_dict(row) -> dict:
    if row is None:
        return {}
    return {
        "base_url": row.base_url,
        "model": row.model,
        "api_key": row.api_key,
        "model_voice": getattr(row, "voice", ""),
    }


def make_stream(member: Member, user_text: str, source: str):
    """构造 SSE 生成器：编排器事件 + 心跳 + 落库。"""

    async def event_stream():
        queue: asyncio.Queue = asyncio.Queue()

        async def produce():
            try:
                profile, persona, llm_cfg, tts_cfg, history = await _load_context(
                    member, user_text
                )
                orchestrator = Orchestrator(profile, persona, llm_cfg, tts_cfg)
                reply_all = ""
                async for event in orchestrator.run(history):
                    await queue.put(sse(event))
                    if event.get("type") == "done":
                        reply_all = event.get("reply", "")
                # 落库（失败不影响对话）
                try:
                    await save_log(
                        member.family_id, member.id, member.display_name,
                        user_text, reply_all, source,
                    )
                except Exception:  # noqa: BLE001
                    pass
            except Exception as e:  # noqa: BLE001
                await queue.put(error_event(f"服务器开小差了：{e}"))
            finally:
                await queue.put(None)  # 结束标记

        producer = asyncio.create_task(produce())
        heartbeat = asyncio.create_task(heartbeat_loop(queue, settings.heartbeat_seconds))
        try:
            while True:
                item = await queue.get()
                if item is None:
                    break
                yield item
        finally:
            heartbeat.cancel()
            if not producer.done():
                producer.cancel()

    return event_stream()


def sse_response(gen) -> StreamingResponse:
    return StreamingResponse(
        gen,
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # 关键：告诉 Nginx 别缓冲 SSE
        },
    )


@router.post("/text")
async def chat_text(req: ChatTextRequest, member: Member = Depends(get_current_member)):
    return sse_response(make_stream(member, req.text, source="text"))


@router.post("/audio")
async def chat_audio(
    file: UploadFile,
    member: Member = Depends(get_current_member),
):
    """云端兜底 ASR：先转写，再走同一条编排链。"""
    audio_bytes = await file.read()
    if not audio_bytes:
        return sse_response(_wrap(sse(error_event("没有收到声音，再试一次好不好？"))))

    async def stream():
        # 取 ASR 配置
        async with SessionLocal() as session:
            key = (await session.execute(
                select(ProviderKey).where(
                    ProviderKey.family_id == member.family_id,
                    ProviderKey.provider == "asr",
                )
            )).scalar_one_or_none()
        if key is None or not key.api_key or not key.model:
            yield sse(error_event("云端耳朵还没配置好，请爸爸到管理面板设置 ASR"))
            return
        try:
            text = await transcribe(key.base_url, key.api_key, key.model, audio_bytes)
        except AsrError as e:
            yield sse(error_event(f"云端听写失败：{e}"))
            return
        if not text:
            yield sse(error_event("莱德还是没听清，再大声说一次好不好？"))
            return
        # 把识别结果也推给 App（界面上能看到"听到的话"）
        yield sse({"type": "asr", "text": text})
        async for chunk in make_stream(member, text, source="audio"):
            yield chunk

    return sse_response(stream())


async def _wrap(event: str):
    yield event
