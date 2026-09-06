"""流式对话编排器：LLM 边出 token → 按句切分 → TTS 边合成 → SSE 边推送。

事件协议（与 App 端 BffClient 约定）：
  {"type": "reply", "text": "…"}                  一句完整的话（总是发送）
  {"type": "audio", "data": "<base64 mp3>"}       该句的克隆音色音频（配置了云 TTS 才有）
  {"type": "done", "reply": "全文"}                本轮结束
  {"type": "error", "message": "…"}               出错（App 用本地 TTS 朗读兜底文案）
"""
import asyncio
import base64
import json
import time

from . import llm as llm_mod
from . import tts as tts_mod
from .config import get_settings
from .persona import build_system_prompt

settings = get_settings()

SENTENCE_END = "。！？!?；;\n"


def clean_sentence(sentence: str) -> str:
    """去掉 Markdown 符号；清洗后为空表示跳过该句。"""
    return sentence.replace("*", "").replace("#", " ").strip()


class Orchestrator:
    def __init__(self, profile: dict, persona: dict, llm_cfg: dict, tts_cfg: dict):
        self.profile = profile
        self.persona = persona
        self.llm_cfg = llm_cfg
        self.tts_cfg = tts_cfg

    async def run(self, history: list[dict]):
        """异步生成 SSE 事件流。history 最后一条是本次用户消息。"""
        user_text = next((m["content"] for m in reversed(history) if m["role"] == "user"), "")
        system_prompt = build_system_prompt(self.profile, self.persona)

        llm_ready = bool(self.llm_cfg.get("api_key") and self.llm_cfg.get("model"))
        tts_ready = bool(self.tts_cfg.get("api_key") and self.tts_cfg.get("model"))

        # 首个事件：告诉 App 本轮是否有云端音频（决定 App 用音频播放还是本地 TTS）
        yield {"type": "meta", "tts": tts_ready}

        # 逐句推送：句子一到就发 reply（+ 可选 audio），不等全文
        if not llm_ready:
            # 云端 LLM 未配置：兜底应答（照样过 TTS，保持协议一致）
            full = llm_mod.make_stub_reply(user_text)
            async for event in self._emit_by_sentence(full, tts_ready):
                yield event
            yield done_event(full)
            return

        t0 = time.monotonic()
        t_first: float | None = None
        pending = ""
        full_parts: list[str] = []
        tts_tasks: list[asyncio.Task] = []  # 按句序；多句 TTS 并行合成，按序收发
        n_sentences = 0

        try:
            try:
                async for delta in llm_mod.stream_chat(
                    self.llm_cfg.get("base_url", ""),
                    self.llm_cfg["api_key"],
                    self.llm_cfg["model"],
                    system_prompt,
                    history,
                ):
                    if t_first is None:
                        t_first = time.monotonic() - t0
                    full_parts.append(delta)
                    pending += delta
                    # 完整句子立刻发 reply，同时为它开一个 TTS 任务（不等前一句合成完）
                    while True:
                        idx = next((i for i, ch in enumerate(pending) if ch in SENTENCE_END), -1)
                        if idx < 0:
                            break
                        sentence = clean_sentence(pending[: idx + 1])
                        pending = pending[idx + 1:]
                        if not sentence:
                            continue
                        n_sentences += 1
                        yield {"type": "reply", "text": sentence}
                        if tts_ready:
                            tts_tasks.append(self._start_tts(sentence))
                    # 已合完的音频按序发出（不阻塞 LLM 消费）
                    while tts_tasks and tts_tasks[0].done() and not tts_tasks[0].cancelled():
                        for event in _task_events(tts_tasks.pop(0)):
                            yield event
            except Exception as e:  # noqa: BLE001 —— 任何厂商异常都转成 SSE error 事件
                print(f"[orchestrator] LLM 失败: {e}", flush=True)
                yield error_event(f"莱德的大脑连接不上：{e}")
                return

            if pending.strip():
                sentence = clean_sentence(pending)
                if sentence:
                    n_sentences += 1
                    yield {"type": "reply", "text": sentence}
                    if tts_ready:
                        tts_tasks.append(self._start_tts(sentence))

            # LLM 结束：按句序等完剩余音频
            while tts_tasks:
                task = tts_tasks.pop(0)
                try:
                    await task
                except Exception:  # noqa: BLE001 —— 失败细节由 _task_events 统一记录
                    pass
                for event in _task_events(task):
                    yield event

            dt = time.monotonic() - t0
            first = f"首字 {t_first:.2f}s，" if t_first is not None else ""
            print(f"[orchestrator] 整轮完成 {dt:.2f}s（{first}共{n_sentences}句）", flush=True)
            yield done_event("".join(full_parts))
        finally:
            for t in tts_tasks:
                t.cancel()

    def _start_tts(self, sentence: str) -> asyncio.Task:
        return asyncio.create_task(
            tts_mod.synthesize(
                self.tts_cfg.get("base_url", ""),
                self.tts_cfg["api_key"],
                self.tts_cfg["model"],
                sentence,
                self.tts_cfg.get("model_voice", ""),
            )
        )

    async def _emit_by_sentence(self, text: str, tts_ready: bool):
        start = 0
        for i, ch in enumerate(text):
            if ch in SENTENCE_END:
                async for event in self._emit_sentence(text[start: i + 1], tts_ready):
                    yield event
                start = i + 1
        if start < len(text):
            async for event in self._emit_sentence(text[start:], tts_ready):
                yield event

    async def _emit_sentence(self, sentence: str, tts_ready: bool):
        cleaned = clean_sentence(sentence)
        if not cleaned:
            return
        yield {"type": "reply", "text": cleaned}
        if tts_ready:
            try:
                audio = await tts_mod.synthesize(
                    self.tts_cfg.get("base_url", ""),
                    self.tts_cfg["api_key"],
                    self.tts_cfg["model"],
                    cleaned,
                    self.tts_cfg.get("model_voice", ""),
                )
                if audio:
                    yield {
                        "type": "audio",
                        "data": base64.b64encode(audio).decode("ascii"),
                    }
            except Exception as e:  # noqa: BLE001 —— TTS 失败不致命，App 用本地 TTS 兜底
                print(f"[orchestrator] TTS 失败: {e}", flush=True)
                yield error_event(f"莱德的声音服务出了点问题：{e}")


def done_event(reply: str) -> dict:
    return {"type": "done", "reply": reply}


def error_event(message: str) -> dict:
    return {"type": "error", "message": message}


def _task_events(task: asyncio.Task) -> list[dict]:
    """已完成的 TTS 任务 → SSE 事件（音频或错误）。"""
    try:
        audio = task.result()
    except Exception as e:  # noqa: BLE001
        print(f"[orchestrator] TTS 失败: {e}", flush=True)
        return [error_event(f"莱德的声音服务出了点问题：{e}")]
    if audio:
        return [{"type": "audio", "data": base64.b64encode(audio).decode("ascii")}]
    return []


def sse(obj: dict) -> str:
    return f"data: {json.dumps(obj, ensure_ascii=False)}\n\n"


async def heartbeat_loop(queue: asyncio.Queue, interval: float):
    """SSE 保活：定期发注释行，防止代理/防火墙掐断长连接。"""
    while True:
        await asyncio.sleep(interval)
        await queue.put(": ping\n\n")
