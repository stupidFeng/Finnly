package com.ryder.buddy.voice

import android.content.Context
import android.speech.tts.TextToSpeech
import android.speech.tts.UtteranceProgressListener
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import java.util.Locale
import java.util.concurrent.atomic.AtomicInteger

/**
 * 语音合成抽象。默认实现用系统 TTS，开箱即用。
 *
 * TODO(升级)：接入火山引擎「声音复刻」克隆莱德音色后，替换为流式云 TTS 实现。
 * 届时 say 出去的每句话都换成莱德的声音，上层无需改动。
 */
interface TtsClient {
    /** 中文 TTS 是否初始化成功 */
    val ready: StateFlow<Boolean>

    /** 是否还有语音在播（用于状态机从 Speaking 回到 Idle） */
    val busy: StateFlow<Boolean>

    /** 朗读一段文本；多次调用按队列顺序播放 */
    fun speak(text: String)

    /** 立即停止（孩子打断莱德时调用） */
    fun stop()

    fun destroy()
}

/** 系统自带中文 TTS */
class AndroidTtsClient(context: Context) : TtsClient {

    private val _ready = MutableStateFlow(false)
    override val ready = _ready.asStateFlow()

    private val _busy = MutableStateFlow(false)
    override val busy = _busy.asStateFlow()

    private val active = AtomicInteger(0)
    private val queuedBeforeInit = mutableListOf<String>()
    private var utteranceSeq = 0

    private val progressListener = object : UtteranceProgressListener() {
        override fun onStart(utteranceId: String?) {
            _busy.value = true
        }

        override fun onDone(utteranceId: String?) = settle()

        override fun onError(utteranceId: String?) = settle()
    }

    private val tts = TextToSpeech(context.applicationContext) { status ->
        if (status == TextToSpeech.SUCCESS) {
            val result = tts.setLanguage(Locale.SIMPLIFIED_CHINESE)
            val ok = result != TextToSpeech.LANG_MISSING_DATA &&
                result != TextToSpeech.LANG_NOT_SUPPORTED
            if (ok) {
                tts.setOnUtteranceProgressListener(progressListener)
                _ready.value = true
                synchronized(queuedBeforeInit) {
                    queuedBeforeInit.forEach { doSpeak(it) }
                    queuedBeforeInit.clear()
                }
            }
        }
    }

    private fun settle() {
        if (active.decrementAndGet() <= 0) {
            active.set(0)
            _busy.value = false
        }
    }

    override fun speak(text: String) {
        val trimmed = text.trim()
        if (trimmed.isEmpty()) return
        if (!_ready.value) {
            // 初始化完成前先缓存，初始化成功后统一播出（最多 4 条，防止堆积）
            synchronized(queuedBeforeInit) {
                if (queuedBeforeInit.size < 4) queuedBeforeInit.add(trimmed)
            }
            return
        }
        doSpeak(trimmed)
    }

    private fun doSpeak(text: String) {
        active.incrementAndGet()
        _busy.value = true
        utteranceSeq++
        tts.speak(text, TextToSpeech.QUEUE_ADD, null, "ryder-$utteranceSeq")
    }

    override fun stop() {
        synchronized(queuedBeforeInit) { queuedBeforeInit.clear() }
        active.set(0)
        _busy.value = false
        tts.stop()
    }

    override fun destroy() {
        active.set(0)
        _busy.value = false
        tts.shutdown()
    }
}
