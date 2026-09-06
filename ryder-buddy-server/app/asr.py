"""ASR 代理：OpenAI 兼容 /audio/transcriptions（讯飞/豆包/GLM 均有兼容端点）。

这是「识别不准时上传音频再听一遍」的云端兜底路径，平时 App 走本地 ASR。
"""
import asyncio
import re

import httpx


class AsrError(RuntimeError):
    pass


# 实测（2026-09）：SenseVoiceSmall 偶发整体故障——多数请求挂起不响应，
# 同平台其他 ASR 模型不受影响（不同 GPU 池）。网络故障时按序自动换模型：
# 配置的主模型 → 另一个候选。两个都实测可用，谁当主模型另一个就是兜底。
ASR_MODELS = ("FunAudioLLM/SenseVoiceSmall", "Qwen/Qwen3-ASR-1.7B")

# SenseVoice 会在识别结果里追加情绪符号（😊😡 等），清掉再进 LLM
_EMOJI_RE = re.compile(
    "[\U0001F000-\U0001FAFF\U00002600-\U000027BF\u2B00-\u2BFF\uFE0F\u200D]+"
)


def _clean(text: str) -> str:
    return _EMOJI_RE.sub("", text).strip()


async def _transcribe_once(
    base_url: str,
    api_key: str,
    model: str,
    audio_bytes: bytes,
    filename: str,
) -> str:
    url = base_url.rstrip("/") + "/audio/transcriptions"
    headers = {"Authorization": f"Bearer {api_key}"}
    files = {"file": (filename, audio_bytes)}
    data = {"model": model, "language": "zh"}

    async with httpx.AsyncClient(timeout=httpx.Timeout(10, read=15)) as client:
        resp = await client.post(url, headers=headers, files=files, data=data)
    if resp.status_code != 200:
        raise AsrError(f"ASR HTTP {resp.status_code}: {resp.text[:200]}")
    return _clean(resp.json().get("text", ""))


async def transcribe(
    base_url: str,
    api_key: str,
    model: str,
    audio_bytes: bytes,
    filename: str = "audio.wav",
) -> str:
    """语音转文字；主模型挂起/断连时自动换兜底模型再试一次。

    非 200（Key 错误等配置问题）立即抛错不兜底——换模型也治不了配置。
    """
    candidates = [model, *(m for m in ASR_MODELS if m != model)]
    last_err: Exception | None = None
    for i, candidate in enumerate(candidates):
        if i:
            await asyncio.sleep(0.3)
        try:
            return await _transcribe_once(
                base_url, api_key, candidate, audio_bytes, filename,
            )
        except httpx.TransportError as e:  # ReadTimeout / ConnectError 等网络层故障
            last_err = e
            print(f"[asr] {candidate} 网络故障: {e!r}，尝试换下一个模型", flush=True)
    raise AsrError(f"ASR 网络故障（主模型和兜底模型都失败）: {last_err!r}")
