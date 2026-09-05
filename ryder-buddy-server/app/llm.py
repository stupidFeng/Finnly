"""LLM 代理：OpenAI 兼容流式接口（DeepSeek / GLM / 豆包 / 通义通吃）。"""
import json
from collections.abc import AsyncIterator

import httpx


class LlmError(RuntimeError):
    pass


async def stream_chat(
    base_url: str,
    api_key: str,
    model: str,
    system_prompt: str,
    history: list[dict],
) -> AsyncIterator[str]:
    """流式对话，逐 token yield。history 为 [{role, content}, ...]，不含 system。"""
    messages = [{"role": "system", "content": system_prompt}, *history]
    payload = {
        "model": model,
        "messages": messages,
        "stream": True,
        "temperature": 0.8,
        "max_tokens": 200,
    }
    url = base_url.rstrip("/") + "/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}"}

    async with httpx.AsyncClient(timeout=httpx.Timeout(10, read=60)) as client:
        async with client.stream("POST", url, json=payload, headers=headers) as resp:
            if resp.status_code != 200:
                body = (await resp.aread()).decode(errors="replace")[:200]
                raise LlmError(f"LLM HTTP {resp.status_code}: {body}")
            async for line in resp.aiter_lines():
                if not line.startswith("data:"):
                    continue
                data = line[5:].strip()
                if not data or data == "[DONE]":
                    continue
                try:
                    obj = json.loads(data)
                    delta = obj["choices"][0]["delta"].get("content", "")
                except (json.JSONDecodeError, KeyError, IndexError):
                    continue
                if delta:
                    yield delta


def make_stub_reply(user_text: str) -> str:
    """云端 Key 未配置时的兜底应答（与 App 离线演示同一套话术）。"""
    if any(k in user_text for k in ("怕", "哭", "噩梦")):
        return "我知道你有点难过。莱德陪着你呢！抱抱你最喜欢的小玩偶，好不好？"
    if any(k in user_text for k in ("故事", "讲")):
        return "好呀！莱德讲个小故事。从前有只勇敢的小狗狗，帮迷路的小猫咪找到了家。小狗狗说，没有困难的任务，只有勇敢的狗狗！"
    if any(k in user_text for k in ("唱歌", "歌")):
        return "一闪一闪亮晶晶，满天都是小星星！莱德唱得好不好听呀？"
    if any(k in user_text for k in ("睡觉", "晚安")):
        return "晚安啦！闭上眼睛，莱德和狗狗们会守护你的梦！"
    if any(k in user_text for k in ("汪汪队", "莱德")):
        return "没错！我就是莱德队长！毛毛、阿奇它们都在冒险湾等你哦！"
    if any(k in user_text for k in ("你好", "嗨", "哈喽")):
        return "你好呀！我是莱德队长！今天想和莱德做什么呀？"
    return "哇！你说得真棒！能再告诉莱德一件今天开心的事吗？"
