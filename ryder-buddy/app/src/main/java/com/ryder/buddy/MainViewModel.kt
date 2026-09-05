package com.ryder.buddy

import android.Manifest
import android.app.Application
import android.content.pm.PackageManager
import androidx.core.content.ContextCompat
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.ryder.buddy.data.MemoryProfile
import com.ryder.buddy.data.ServerConfig
import com.ryder.buddy.data.SettingsRepository
import com.ryder.buddy.voice.AndroidTtsClient
import com.ryder.buddy.voice.AsrClient
import com.ryder.buddy.voice.AudioRecorder
import com.ryder.buddy.voice.BffClient
import com.ryder.buddy.voice.BffEvent
import com.ryder.buddy.voice.BffHistoryPage
import com.ryder.buddy.voice.BffKeyMasked
import com.ryder.buddy.voice.BffMember
import com.ryder.buddy.voice.BffPersona
import com.ryder.buddy.voice.ChatMessage
import com.ryder.buddy.voice.CloudAudioPlayer
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
import kotlinx.serialization.encodeToString

/** 对话状态机：空闲 → 聆听 → 思考 → 说话 → 空闲 */
enum class TalkState { Idle, Listening, Thinking, Speaking }

/**
 * 双模式：
 *  - 服务器模式（ServerConfig 已配置）：ASR 在本地，LLM/记忆/历史/克隆音色全部走家庭后端
 *  - 离线演示模式：StubLlmClient + 本地 TTS，不连任何服务器
 */
class MainViewModel(application: Application) : AndroidViewModel(application) {

    private val repo = SettingsRepository(application)
    private val asr: AsrClient = SpeechRecognizerAsrClient(application)
    private val tts: TtsClient = AndroidTtsClient(application)
    private val cloudAudio = CloudAudioPlayer(application)
    private val recorder = AudioRecorder()

    private var bff: BffClient? = null

    val profile: StateFlow<MemoryProfile?> =
        repo.profile.stateIn(viewModelScope, SharingStarted.Eagerly, null)
    val serverConfig: StateFlow<ServerConfig?> =
        repo.serverConfig.stateIn(viewModelScope, SharingStarted.Eagerly, null)

    val asrAvailable: Boolean get() = asr.isAvailable
    val ttsReady: StateFlow<Boolean> get() = tts.ready
    val cloudAudioBusy: StateFlow<Boolean> get() = cloudAudio.busy

    private val _talkState = MutableStateFlow(TalkState.Idle)
    val talkState: StateFlow<TalkState> = _talkState.asStateFlow()

    private val _heard = MutableStateFlow("")
    val heard: StateFlow<String> = _heard.asStateFlow()

    private val _lastReply = MutableStateFlow("")
    val lastReply: StateFlow<String> = _lastReply.asStateFlow()

    private val localHistory = mutableListOf<ChatMessage>() // 仅离线演示模式使用
    private var talkJob: Job? = null
    private var speakJob: Job? = null

    private fun bffClient(url: String? = null): BffClient {
        val base = url ?: serverConfig.value?.baseUrl.orEmpty()
        return bff?.takeIf { it === bff && serverConfig.value?.baseUrl == base }
            ?: BffClient(base).also {
                bff = it
            }
    }

    // ---------- 孩子对话 ----------

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
        cloudAudio.stop()
        _heard.value = ""
        _talkState.value = TalkState.Listening
        // 并行录音：本地识别失败时把这份音频传给云端"再听一遍"
        recorder.start()
        asr.startListening(
            onPartial = { _heard.value = it },
            onFinal = { text ->
                recorder.discard() // 识别成功，不需要兜底了
                respond(text)
            },
            onError = { _ ->
                val wav = recorder.stop()
                if (wav != null && isServerMode()) {
                    // 云端兜底：让服务端的儿童 ASR 再听一遍
                    respondWithAudio(wav)
                } else {
                    speakRyder("莱德没有听清，再大声说一次好不好？")
                }
            },
        )
    }

    fun stopListening() {
        if (_talkState.value == TalkState.Listening) asr.stopListening()
    }

    private fun isServerMode(): Boolean =
        serverConfig.value?.let { it.baseUrl.isNotBlank() && it.token.isNotBlank() } == true

    /** 服务器模式：文本主路径 */
    private fun respond(userText: String) {
        if (!isServerMode()) {
            respondOffline(userText)
            return
        }
        val config = serverConfig.value!!
        _talkState.value = TalkState.Thinking
        _lastReply.value = ""

        talkJob = viewModelScope.launch {
            try {
                var serverTts = false
                val reply = bffClient().chatText(config.token, userText) { event ->
                    when (event) {
                        is BffEvent.Meta -> serverTts = event.serverTts
                        is BffEvent.Asr -> _heard.value = event.text
                        is BffEvent.Reply -> {
                            _lastReply.value += event.text
                            if (!serverTts) tts.speak(event.text) // 无云端音色用本地 TTS
                        }
                        is BffEvent.Audio -> cloudAudio.enqueue(event.mp3)
                        is BffEvent.Done -> _lastReply.value = event.reply
                        is BffEvent.Error -> {
                            tts.speak("哎呀，莱德的对讲机出了点小问题，等一下再试试好不好？")
                        }
                    }
                    if (_talkState.value != TalkState.Speaking &&
                        (_lastReply.value.isNotBlank() || cloudAudio.busy.value)
                    ) {
                        _talkState.value = TalkState.Speaking
                    }
                }
                _lastReply.value = reply.ifBlank { _lastReply.value }
                awaitSpeakDone()
                if (_talkState.value == TalkState.Speaking) _talkState.value = TalkState.Idle
            } catch (e: CancellationException) {
                throw e
            } catch (e: Exception) {
                // 服务器不可达：整轮退回离线演示，孩子无感
                respondOffline(userText)
            }
        }
    }

    /** 服务器模式：本地识别失败，上传录音走云端 ASR 兜底 */
    private fun respondWithAudio(wav: ByteArray) {
        val config = serverConfig.value ?: return
        _talkState.value = TalkState.Thinking
        _heard.value = "（让云端再听一遍…）"

        talkJob = viewModelScope.launch {
            try {
                var serverTts = false
                val reply = bffClient().chatAudio(config.token, wav) { event ->
                    when (event) {
                        is BffEvent.Meta -> serverTts = event.serverTts
                        is BffEvent.Asr -> _heard.value = event.text
                        is BffEvent.Reply -> {
                            _lastReply.value += event.text
                            if (!serverTts) tts.speak(event.text)
                        }
                        is BffEvent.Audio -> cloudAudio.enqueue(event.mp3)
                        is BffEvent.Done -> _lastReply.value = event.reply
                        is BffEvent.Error -> tts.speak("莱德还是没听清，再大声说一次好不好？")
                    }
                    if (_talkState.value != TalkState.Speaking &&
                        (_lastReply.value.isNotBlank() || cloudAudio.busy.value)
                    ) {
                        _talkState.value = TalkState.Speaking
                    }
                }
                _lastReply.value = reply.ifBlank { _lastReply.value }
                awaitSpeakDone()
                if (_talkState.value == TalkState.Speaking) _talkState.value = TalkState.Idle
            } catch (e: CancellationException) {
                throw e
            } catch (e: Exception) {
                speakRyder("莱德没有听清，再大声说一次好不好？")
            }
        }
    }

    /** 离线演示模式：本地 Stub + 本地 TTS（也是服务器故障时的兜底） */
    private fun respondOffline(userText: String) {
        _talkState.value = TalkState.Thinking
        _lastReply.value = ""

        talkJob = viewModelScope.launch {
            try {
                val reply = VoicePipeline(StubLlmClient(), tts).respond(
                    systemPrompt = "",
                    history = localHistory.toList() + ChatMessage("user", userText),
                    onReplyStarted = { _talkState.value = TalkState.Speaking },
                )
                _lastReply.value = reply
                localHistory += listOf(
                    ChatMessage("user", userText),
                    ChatMessage("assistant", reply),
                )
                while (localHistory.size > MAX_HISTORY) localHistory.removeFirst()
                awaitSpeakDone()
                if (_talkState.value == TalkState.Speaking) _talkState.value = TalkState.Idle
            } catch (e: CancellationException) {
                throw e
            } catch (_: Exception) {
                speakRyder("哎呀，莱德的对讲机出了点小问题，等一下再试试好不好？")
            }
        }
    }

    /** 用莱德的声音说一句话（错误安抚 / 试听） */
    fun speakRyder(text: String) {
        tts.stop()
        cloudAudio.stop()
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

    private suspend fun awaitSpeakDone() {
        withTimeoutOrNull(60_000) {
            tts.busy.first { !it }
        }
        withTimeoutOrNull(60_000) {
            cloudAudio.busy.first { !it }
        }
    }

    // ---------- 家长面板：服务器 ----------

    fun login(baseUrl: String, username: String, password: String, onResult: (String?) -> Unit) {
        viewModelScope.launch {
            try {
                val auth = BffClient(baseUrl).login(username, password)
                repo.saveServerConfig(
                    ServerConfig(
                        baseUrl = baseUrl,
                        token = auth.token,
                        role = auth.role,
                        displayName = auth.displayName,
                    )
                )
                refreshProfileFromServer()
                onResult(null)
            } catch (e: Exception) {
                onResult(e.message ?: "登录失败")
            }
        }
    }

    fun join(baseUrl: String, inviteCode: String, displayName: String, onResult: (String?) -> Unit) {
        viewModelScope.launch {
            try {
                val auth = BffClient(baseUrl).join(inviteCode, displayName)
                repo.saveServerConfig(
                    ServerConfig(
                        baseUrl = baseUrl,
                        token = auth.token,
                        role = auth.role,
                        displayName = auth.displayName,
                    )
                )
                refreshProfileFromServer()
                onResult(null)
            } catch (e: Exception) {
                onResult(e.message ?: "加入失败")
            }
        }
    }

    fun logout() {
        viewModelScope.launch { repo.clearServerConfig() }
    }

    /** 拉取服务端权威记忆档案，更新本地缓存 */
    fun refreshProfileFromServer() {
        val config = serverConfig.value ?: return
        viewModelScope.launch {
            try {
                val remote = bffClient().getProfile(config.token)
                val json = kotlinx.serialization.json.Json { ignoreUnknownKeys = true }
                val fetched = json.decodeFromString<MemoryProfile>(remote.toString())
                repo.saveProfile(fetched)
            } catch (_: Exception) {
                // 网络问题保留本地缓存
            }
        }
    }

    /** 父亲保存记忆档案：写服务端 + 更新本地缓存 */
    fun saveProfileRemote(profile: MemoryProfile, onResult: (String?) -> Unit) {
        val config = serverConfig.value ?: return
        viewModelScope.launch {
            try {
                val json = kotlinx.serialization.json.Json {
                    ignoreUnknownKeys = true
                    encodeDefaults = true
                }
                bffClient().putProfile(config.token, json.encodeToString(profile))
                repo.saveProfile(profile)
                onResult(null)
            } catch (e: Exception) {
                onResult(e.message ?: "保存失败")
            }
        }
    }

    fun saveProfileLocal(profile: MemoryProfile) {
        viewModelScope.launch { repo.saveProfile(profile) }
    }

    // ---------- 家长面板：父亲管理 ----------

    fun loadKeys(onResult: (List<BffKeyMasked>?, String?) -> Unit) {
        val config = serverConfig.value ?: return
        viewModelScope.launch {
            try {
                onResult(bffClient().getKeys(config.token), null)
            } catch (e: Exception) {
                onResult(null, e.message)
            }
        }
    }

    fun saveKey(key: BffKeyMasked, onResult: (String?) -> Unit) {
        val config = serverConfig.value ?: return
        viewModelScope.launch {
            try {
                bffClient().putKey(config.token, key)
                onResult(null)
            } catch (e: Exception) {
                onResult(e.message ?: "保存失败")
            }
        }
    }

    fun loadPersona(onResult: (BffPersona?) -> Unit) {
        val config = serverConfig.value ?: return
        viewModelScope.launch {
            try {
                onResult(bffClient().getPersona(config.token))
            } catch (_: Exception) {
                onResult(null)
            }
        }
    }

    fun savePersona(persona: BffPersona, onResult: (String?) -> Unit) {
        val config = serverConfig.value ?: return
        viewModelScope.launch {
            try {
                bffClient().putPersona(config.token, persona)
                onResult(null)
            } catch (e: Exception) {
                onResult(e.message ?: "保存失败")
            }
        }
    }

    fun createInvite(onResult: (String?) -> Unit) {
        val config = serverConfig.value ?: return
        viewModelScope.launch {
            try {
                onResult(bffClient().createInvite(config.token))
            } catch (e: Exception) {
                onResult(null)
            }
        }
    }

    fun loadMembers(onResult: (List<BffMember>?) -> Unit) {
        val config = serverConfig.value ?: return
        viewModelScope.launch {
            try {
                onResult(bffClient().getMembers(config.token))
            } catch (_: Exception) {
                onResult(null)
            }
        }
    }

    fun loadHistory(limit: Int = 50, offset: Int = 0, onResult: (BffHistoryPage?) -> Unit) {
        val config = serverConfig.value ?: return
        viewModelScope.launch {
            try {
                onResult(bffClient().getHistory(config.token, limit, offset))
            } catch (_: Exception) {
                onResult(null)
            }
        }
    }

    override fun onCleared() {
        asr.destroy()
        tts.destroy()
        cloudAudio.stop()
        super.onCleared()
    }

    companion object {
        private const val MAX_HISTORY = 12
    }
}
