"""ASR 代理：OpenAI 兼容 /audio/transcriptions（讯飞/豆包/GLM 均有兼容端点）。

这是「识别不准时上传音频再听一遍」的云端兜底路径，平时 App 走本地 ASR。
"""
import asyncio

import httpx


class AsrError(RuntimeError):
    pass


async def transcribe(
    base_url: str,
    api_key: str,
    model: str,
    audio_bytes: bytes,
    filename: str = "audio.wav",
) -> str:
    """语音转文字；网络层故障（挂起/断连）换新连接自动重试一次。

    实测硅基流动 ASR 偶发挂起不响应（ReadTimeout 干等 60s），
    所以单次 read 超时收紧到 20s，失败快速换连接重试。
    """
    url = base_url.rstrip("/") + "/audio/transcriptions"
    headers = {"Authorization": f"Bearer {api_key}"}
    files = {"file": (filename, audio_bytes)}
    data = {"model": model, "language": "zh"}

    last_err: Exception | None = None
    for attempt in range(2):
        if attempt:
            await asyncio.sleep(0.5)
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(10, read=20)) as client:
                resp = await client.post(url, headers=headers, files=files, data=data)
        except httpx.TransportError as e:  # ReadTimeout / ConnectError 等网络层故障
            last_err = e
            print(f"[asr] 第 {attempt + 1} 次尝试网络故障: {e!r}", flush=True)
            continue
        if resp.status_code != 200:
            raise AsrError(f"ASR HTTP {resp.status_code}: {resp.text[:200]}")
        return resp.json().get("text", "").strip()
    raise AsrError(f"ASR 网络故障（重试后仍失败）: {last_err!r}")
