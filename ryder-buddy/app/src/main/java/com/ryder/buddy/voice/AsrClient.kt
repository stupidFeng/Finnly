package com.ryder.buddy.voice

import android.content.Context
import android.content.Intent
import android.os.Bundle
import android.speech.RecognitionListener
import android.speech.RecognizerIntent
import android.speech.SpeechRecognizer

/**
 * 语音识别抽象。默认实现用系统 SpeechRecognizer，开箱即用。
 *
 * TODO(升级)：接入讯飞儿童识别引擎或豆包流式 ASR——幼儿口齿不清，
 * 儿童声学模型的识别率会明显更好。替换本实现即可，上层无需改动。
 */
interface AsrClient {
    val isAvailable: Boolean

    /** 开始聆听。onPartial 为中间结果（用于界面实时显示），onFinal 为最终结果 */
    fun startListening(
        onPartial: (String) -> Unit,
        onFinal: (String) -> Unit,
        onError: (userFriendlyMessage: String) -> Unit,
    )

    /** 松开按钮时调用，触发最终识别结果 */
    fun stopListening()

    fun destroy()
}

/** 系统自带语音识别（依赖设备的语音服务，多数国产 ROM 亦可用） */
class SpeechRecognizerAsrClient(private val context: Context) : AsrClient {

    override val isAvailable: Boolean
        get() = SpeechRecognizer.isRecognitionAvailable(context)

    private var recognizer: SpeechRecognizer? = null
    private var onPartial: ((String) -> Unit)? = null
    private var onFinal: ((String) -> Unit)? = null
    private var onError: ((String) -> Unit)? = null

    override fun startListening(
        onPartial: (String) -> Unit,
        onFinal: (String) -> Unit,
        onError: (String) -> Unit,
    ) {
        this.onPartial = onPartial
        this.onFinal = onFinal
        this.onError = onError
        val r = recognizer ?: SpeechRecognizer.createSpeechRecognizer(context).also { recognizer = it }
        r.setRecognitionListener(listener)
        r.startListening(listenIntent())
    }

    override fun stopListening() {
        recognizer?.stopListening()
    }

    override fun destroy() {
        recognizer?.destroy()
        recognizer = null
    }

    private fun listenIntent() = Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH).apply {
        putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL, RecognizerIntent.LANGUAGE_MODEL_FREE_FORM)
        putExtra(RecognizerIntent.EXTRA_LANGUAGE, "zh-CN")
        putExtra(RecognizerIntent.EXTRA_LANGUAGE_PREFERENCE, "zh-CN")
        putExtra(RecognizerIntent.EXTRA_PARTIAL_RESULTS, true)
        putExtra(RecognizerIntent.EXTRA_MAX_RESULTS, 1)
    }

    private val listener = object : RecognitionListener {
        override fun onReadyForSpeech(params: Bundle?) {}
        override fun onBeginningOfSpeech() {}
        override fun onRmsChanged(rmsdB: Float) {}
        override fun onBufferReceived(buffer: ByteArray?) {}
        override fun onEndOfSpeech() {}

        override fun onError(error: Int) {
            onError?.invoke(friendlyError(error))
        }

        override fun onResults(results: Bundle?) {
            val text = results?.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION)
                ?.firstOrNull().orEmpty()
            if (text.isNotBlank()) {
                onFinal?.invoke(text)
            } else {
                onError?.invoke(friendlyError(SpeechRecognizer.ERROR_NO_MATCH))
            }
        }

        override fun onPartialResults(partialResults: Bundle?) {
            val text = partialResults?.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION)
                ?.firstOrNull().orEmpty()
            if (text.isNotBlank()) onPartial?.invoke(text)
        }

        override fun onEvent(eventType: Int, params: Bundle?) {}
    }

    /** 把错误码翻译成莱德口吻的话，直接由 TTS 说出来安抚孩子 */
    private fun friendlyError(error: Int): String = when (error) {
        SpeechRecognizer.ERROR_NO_MATCH,
        SpeechRecognizer.ERROR_SPEECH_TIMEOUT -> "莱德没有听清，再大声说一次好不好？"
        SpeechRecognizer.ERROR_RECOGNIZER_BUSY -> "莱德的对讲机忙不过来啦，等一秒再按哦！"
        else -> "哎呀，对讲机出了点小问题，再试一次吧！"
    }
}
