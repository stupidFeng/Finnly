package com.ryder.buddy

import android.Manifest
import android.app.Application
import android.content.pm.PackageManager
import androidx.core.content.ContextCompat
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.ryder.buddy.data.LlmSettings
import com.ryder.buddy.data.MemoryProfile
import com.ryder.buddy.data.SettingsRepository
import com.ryder.buddy.persona.PersonaPromptBuilder
import com.ryder.buddy.voice.AndroidTtsClient
import com.ryder.buddy.voice.AsrClient
import com.ryder.buddy.voice.ChatMessage
import com.ryder.buddy.voice.LlmClient
import com.ryder.buddy.voice.OpenAiCompatibleLlmClient
import com.ryder.buddy.voice.SpeechRecognizerAsrClient
import com.ryder.buddy.voice.StubLlmClient
import com.ryder.buddy.voice.TtsClient
import com.ryder.buddy.voice.VoicePipeline
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Job
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.launch
import kotlinx.coroutines.withTimeoutOrNull

/** 对话状态机：空闲 → 聆听 → 思考 → 说话 → 空闲 */
enum class TalkState { Idle, Listening, Thinking, Speaking }

class MainViewModel(application: Application) : AndroidViewModel(application) {

    private val repo = SettingsRepository(application)
    private val asr: AsrClient = SpeechRecognizerAsrClient(application)
    private val tts: TtsClient = AndroidTtsClient(application)

    /** null 表示 DataStore 尚未加载完成 */
    val profile: StateFlow<MemoryProfile?> =
        repo.profile.stateIn(viewModelScope, SharingStarted.Eagerly, null)
    val llmSettings: StateFlow<LlmSettings?> =
        repo.llmSettings.stateIn(viewModelScope, SharingStarted.Eagerly, null)

    val asrAvailable: Boolean get() = asr.isAvailable
    val ttsReady: StateFlow<Boolean> get() = tts.ready

    private val _talkState = MutableStateFlow(TalkState.Idle)
    val talkState: StateFlow<TalkState> = _talkState.asStateFlow()

    private val _heard = MutableStateFlow("") // ASR 中间结果，界面实时显示
    val heard: StateFlow<String> = _heard.asStateFlow()

    private val _lastReply = MutableStateFlow("")
    val lastReply: StateFlow<String> = _lastReply.asStateFlow()

    private val history = mutableListOf<ChatMessage>()
    private var talkJob: Job? = null
    private var speakJob: Job? = null

    /** 按下大按钮：打断莱德 → 开始聆听 */
    fun startListening() {
        if (ContextCompat.checkSelfPermission(
                getApplication(), Manifest.permission.RECORD_AUDIO
            ) != PackageManager.PERMISSION_GRANTED
        ) return

        if (!asr.isAvailable) {
            speakRyder("哎呀，莱德的对讲机还没装好，请爸爸妈妈到家长面板看看吧！")
            return
        }

        talkJob?.cancel()
        speakJob?.cancel()
        tts.stop()
        _heard.value = ""
        _talkState.value = TalkState.Listening
        asr.startListening(
            onPartial = { _heard.value = it },
            onFinal = ::respond,
            onError = ::speakRyder, // ASR 出错时，让莱德用语音安抚而不是报错
        )
    }

    /** 松开大按钮：触发最终识别结果 */
    fun stopListening() {
        if (_talkState.value == TalkState.Listening) asr.stopListening()
    }

    private fun respond(userText: String) {
        _talkState.value = TalkState.Thinking

        val settings = llmSettings.value ?: LlmSettings()
        val llm: LlmClient = if (settings.useStub || settings.apiKey.isBlank() || settings.model.isBlank()) {
            StubLlmClient()
        } else {
            OpenAiCompatibleLlmClient(settings.baseUrl, settings.apiKey, settings.model)
        }
        val systemPrompt = PersonaPromptBuilder.build(profile.value ?: MemoryProfile())

        talkJob = viewModelScope.launch {
            try {
                _lastReply.value = ""
                val reply = VoicePipeline(llm, tts).respond(
                    systemPrompt = systemPrompt,
                    history = history.toList() + ChatMessage("user", userText),
                    onReplyStarted = { _talkState.value = TalkState.Speaking },
                )
                _lastReply.value = reply
                history += listOf(
                    ChatMessage("user", userText),
                    ChatMessage("assistant", reply),
                )
                while (history.size > MAX_HISTORY) history.removeFirst()

                awaitSpeakDone()
                if (_talkState.value == TalkState.Speaking) _talkState.value = TalkState.Idle
            } catch (e: CancellationException) {
                throw e
            } catch (e: Exception) {
                speakRyder("哎呀，莱德的对讲机出了点小问题，等一下再试试好不好？")
            }
        }
    }

    /** 用莱德的声音说一句话（错误安抚 / 试听） */
    fun speakRyder(text: String) {
        tts.stop()
        _lastReply.value = text
        _talkState.value = TalkState.Speaking
        tts.speak(text)
        speakJob?.cancel()
        speakJob = viewModelScope.launch {
            awaitSpeakDone()
            if (_talkState.value == TalkState.Speaking) _talkState.value = TalkState.Idle
        }
    }

    fun testVoice() {
        speakRyder("你好呀！我是莱德队长！没有困难的任务，只有勇敢的狗狗！")
    }

    fun saveProfile(p: MemoryProfile) {
        viewModelScope.launch { repo.saveProfile(p) }
    }

    fun saveLlmSettings(s: LlmSettings) {
        viewModelScope.launch { repo.saveLlmSettings(s) }
    }

    private suspend fun awaitSpeakDone() {
        withTimeoutOrNull(60_000) { tts.busy.first { !it } }
    }

    override fun onCleared() {
        asr.destroy()
        tts.destroy()
        super.onCleared()
    }

    companion object {
        private const val MAX_HISTORY = 12 // 上下文太长既浪费 token 也提高延迟
    }
}
