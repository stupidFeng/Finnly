"""ASR 代理：OpenAI 兼容 /audio/transcriptions（讯飞/豆包/GLM 均有兼容端点）。

这是「识别不准时上传音频再听一遍」的云端兜底路径，平时 App 走本地 ASR。
"""
import httpx


class AsrError(RuntimeError):
    pass


async def transcribe(
    base_url: str,
    api_key: str,
    model: str,
    audio_bytes: bytes,
    filename: str = "audio.m4a",
) -> str:
    url = base_url.rstrip("/") + "/audio/transcriptions"
    headers = {"Authorization": f"Bearer {api_key}"}
    files = {"file": (filename, audio_bytes)}
    data = {"model": model, "language": "zh"}

    async with httpx.AsyncClient(timeout=httpx.Timeout(10, read=60)) as client:
        resp = await client.post(url, headers=headers, files=files, data=data)
        if resp.status_code != 200:
            raise AsrError(f"ASR HTTP {resp.status_code}: {resp.text[:200]}")
        return resp.json().get("text", "").strip()
