#!/usr/bin/env python3
"""RyderBuddy 服务端诊断脚本。

在宿主机执行（结果直接打印，全部复制发给 AI 分析）：

    docker exec -i ryder-server python - < ryder-buddy-server/scripts/diagnose.py

检查内容：
  1. 容器里跑的是新代码还是旧代码（ASR 文件名 bug 是否修掉）
  2. 数据库里三件套（LLM/TTS/ASR）配置是否完整
  3. TTS 用配置的音色真实合成一句话
  4. ASR 把合成的语音再识别回来（端到端回环）
  5. LLM 真实对话一次
"""

import asyncio
import io
import math
import struct
import wave


def ok(msg: str) -> None:
    print(f"  [OK]   {msg}")


def bad(msg: str) -> None:
    print(f"  [FAIL] {msg}")


def info(msg: str) -> None:
    print(f"  [..]   {msg}")


# ---------- 1. 代码版本 ----------

def check_code() -> None:
    print("\n=== 1. 运行中的代码版本 ===")
    try:
        src = open("/srv/app/routes/chat_routes.py", encoding="utf-8").read()
    except OSError as e:
        bad(f"读不到源码: {e}")
        return
    if 'filename=file.filename or "audio.wav"' in src:
        ok("新代码：ASR 文件名透传修复已生效")
    else:
        bad("旧代码还在跑！App 上传的 WAV 被当成 m4a 发给识别服务，必然识别失败")
        info("修复方法：cd ryder-buddy-server && docker compose up -d --build")


# ---------- 2. 数据库配置 ----------

async def check_db() -> dict | None:
    print("\n=== 2. 数据库配置 ===")
    from sqlalchemy import func, select
    from app.db import ChatLog, Family, Member, ProviderKey, SessionLocal

    cfg: dict = {}
    async with SessionLocal() as session:
        fam = (await session.execute(select(Family))).scalars().first()
        if not fam:
            bad("没有任何家庭记录——App 从未成功登录过这个服务器？")
            return None
        print(f"  家庭: id={fam.id} name={fam.name}")

        members = (await session.execute(
            select(Member).where(Member.family_id == fam.id)
        )).scalars().all()
        for m in members:
            print(f"  成员: {m.display_name}（{m.role}） username={m.username}")

        keys = (await session.execute(
            select(ProviderKey).where(ProviderKey.family_id == fam.id)
        )).scalars().all()
        if not keys:
            bad("provider_keys 表为空！App 家长面板里填的配置没有保存进数据库")
        for k in keys:
            masked = (k.api_key[:10] + "****") if k.api_key else "(空)"
            voice = f" voice={k.voice!r}" if k.provider == "tts" else ""
            print(f"  [{k.provider.upper():3s}] base_url={k.base_url or '(空)'} | "
                  f"model={k.model or '(空)'} | key={masked}{voice}")
            if not (k.base_url and k.model and k.api_key):
                bad(f"{k.provider.upper()} 配置不完整（接口地址/模型/Key 三项都必须有值）")
            cfg[k.provider] = k

        n_logs = (await session.execute(select(func.count(ChatLog.id)))).scalar()
        print(f"  历史对话记录: {n_logs} 条")
        recent = (await session.execute(
            select(ChatLog).order_by(ChatLog.id.desc()).limit(3)
        )).scalars().all()
        for c in recent:
            print(f"    #{c.id} [{c.source}] {c.member_name}: {c.user_text[:20]} -> {c.reply_text[:30]}")
    return cfg


# ---------- 3. TTS ----------

async def test_tts(cfg: dict) -> bytes | None:
    print("\n=== 3. TTS（莱德的声音）===")
    k = cfg.get("tts")
    if k is None:
        bad("没有 TTS 配置记录")
        return None
    from app.tts import synthesize
    try:
        mp3 = await synthesize(k.base_url, k.api_key, k.model, "你好呀，我是莱德队长。", k.voice)
        if mp3:
            note = "（用配置的克隆音色）" if k.voice else "（没配音色！会退回默认音色）"
            ok(f"合成成功 {len(mp3)} 字节 {note}")
            return mp3
        bad("返回空音频（Key 或模型为空时如此）")
    except Exception as e:  # noqa: BLE001
        bad(f"合成失败: {e}")
    return None


# ---------- 4. ASR ----------

def sine_wav(seconds: float = 1.0, freq: int = 440, rate: int = 16000) -> bytes:
    """生成 16k 单声道正弦波 WAV——和 App 上传的录音同格式（内容无语义）。"""
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        frames = bytearray()
        for i in range(int(seconds * rate)):
            frames += struct.pack("<h", int(12000 * math.sin(2 * math.pi * freq * i / rate)))
        w.writeframes(bytes(frames))
    return buf.getvalue()


async def test_asr(cfg: dict, tts_mp3: bytes | None) -> None:
    print("\n=== 4. ASR（云端耳朵）===")
    k = cfg.get("asr")
    if k is None:
        bad("没有 ASR 配置记录——服务器会报『云端耳朵还没配置好』")
        return
    from app.asr import transcribe

    # 回环：真实语音（TTS 刚合成的）应能识别出文字
    if tts_mp3:
        try:
            text = await transcribe(k.base_url, k.api_key, k.model, tts_mp3, filename="audio.mp3")
            if text:
                ok(f"识别正常，回环结果: {text!r}")
            else:
                bad("接口通了但返回空文本——检查 Key 是否正确、账户是否欠费")
        except Exception as e:  # noqa: BLE001
            bad(f"识别失败: {e}")
    else:
        info("跳过语音回环（上一步 TTS 没有产出音频）")

    # 模拟 App 的 WAV 上传：16k 单声道（正弦波无语义，空文本属预期，只验证链路）
    try:
        text = await transcribe(k.base_url, k.api_key, k.model, sine_wav(), filename="audio.wav")
        ok(f"WAV 上传链路正常（正弦波识别为空属预期）: {text!r}")
    except Exception as e:  # noqa: BLE001
        bad(f"WAV 上传链路失败: {e}")


# ---------- 5. LLM ----------

async def test_llm(cfg: dict) -> None:
    print("\n=== 5. LLM（莱德的大脑）===")
    k = cfg.get("llm")
    if k is None:
        bad("没有 LLM 配置记录")
        return
    from app.llm import stream_chat
    try:
        got = ""
        async for delta in stream_chat(
            k.base_url, k.api_key, k.model,
            "你是测试助手。",
            [{"role": "user", "content": "请只回复两个字：收到"}],
        ):
            got += delta
            if len(got) >= 50:
                break
        if got:
            ok(f"LLM 正常: {got[:50]!r}")
        else:
            bad("LLM 连通但返回空内容")
    except Exception as e:  # noqa: BLE001
        bad(f"LLM 失败: {e}")


async def main() -> None:
    print("RyderBuddy 服务端诊断 " + "=" * 40)
    check_code()
    cfg = await check_db()
    if cfg is None:
        print("\n=== 诊断提前结束（数据库无家庭记录） ===")
        return
    tts_mp3 = await test_tts(cfg)
    await test_asr(cfg, tts_mp3)
    await test_llm(cfg)
    print("\n=== 诊断完成，请把上面全部输出复制发回 ===")
    print("=== 另外请附上容器日志: docker logs ryder-server --tail 100 ===")


asyncio.run(main())
