"""TTS 代理：OpenAI 兼容 /speech 接口（豆包、GLM、MiniMax 等均有兼容端点）。

未配置 TTS Key 时返回 None——App 收到 reply 事件后用本地 TTS 朗读，
配置后返回 MP3 字节流，App 直接播放（克隆的莱德音色走这条路）。
"""
import httpx


class TtsError(RuntimeError):
    pass


async def synthesize(
    base_url: str,
    api_key: str,
    model: str,
    text: str,
    voice: str = "",
) -> bytes | None:
    """把一句话合成音频；未配置（Key/模型为空）时返回 None 走本地 TTS。"""
    if not api_key or not model:
        return None
    payload: dict = {"model": model, "input": text, "response_format": "mp3"}
    if voice:
        payload["voice"] = voice
    url = base_url.rstrip("/") + "/audio/speech"
    headers = {"Authorization": f"Bearer {api_key}"}

    async with httpx.AsyncClient(timeout=httpx.Timeout(10, read=30)) as client:
        resp = await client.post(url, json=payload, headers=headers)
        if resp.status_code != 200:
            body = resp.text[:200]
            raise TtsError(f"TTS HTTP {resp.status_code}: {body}")
        if resp.headers.get("content-type", "").startswith("audio"):
            return resp.content
        # 部分服务错误时返回 JSON 却带 200，这里防御一下
        raise TtsError(f"TTS 返回了非音频内容: {resp.text[:200]}")
