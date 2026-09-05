package com.ryder.buddy.voice

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.currentCoroutineContext
import kotlinx.coroutines.ensureActive
import kotlinx.coroutines.withContext
import kotlinx.serialization.Serializable
import kotlinx.serialization.encodeToString
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.booleanOrNull
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.contentOrNull
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import kotlinx.serialization.json.put
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.MultipartBody
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import java.io.IOException
import java.util.concurrent.TimeUnit

/** SSE 事件（与后端 orchestrator 协议一一对应） */
sealed interface BffEvent {
    data class Meta(val serverTts: Boolean) : BffEvent
    data class Asr(val text: String) : BffEvent
    data class Reply(val text: String) : BffEvent
    data class Audio(val mp3: ByteArray) : BffEvent
    data class Done(val reply: String) : BffEvent
    data class Error(val message: String) : BffEvent
}

@Serializable
data class BffAuth(val token: String, val role: String, val displayName: String)

@Serializable
data class BffKeyMasked(
    val provider: String,
    val base_url: String = "",
    val model: String = "",
    val api_key_masked: String = "",
)

@Serializable
data class BffHistoryItem(
    val id: Int,
    val member_name: String,
    val user_text: String,
    val reply_text: String,
    val source: String = "text",
    val created_at: String = "",
)

@Serializable
data class BffHistoryPage(val items: List<BffHistoryItem>, val total: Int)

@Serializable
data class BffMember(val id: Int, val display_name: String, val role: String)

@Serializable
data class BffPersona(
    val characterName: String = "莱德队长",
    val speakingStyle: String = "",
    val safetyRules: String = "",
    val catchphrase: String = "没有困难的任务，只有勇敢的狗狗！",
    val extraPrompt: String = "",
)

/**
 * 家庭后端客户端：REST（登录/管理/历史）+ SSE（流式对话）。
 * App 端唯一的网络出口——不持有任何厂商 API Key。
 */
class BffClient(private var baseUrl: String) {

    private val client = OkHttpClient.Builder()
        .connectTimeout(10, TimeUnit.SECONDS)
        .readTimeout(90, TimeUnit.SECONDS) // SSE 长连接 + TTS 合成可能较慢
        .build()

    private val json = Json {
        ignoreUnknownKeys = true
        encodeDefaults = true
    }

    fun updateBaseUrl(url: String) {
        baseUrl = url
    }

    // ---------- REST ----------

    suspend fun login(username: String, password: String): BffAuth = post(
        path = "/auth/login",
        body = buildJsonObject {
            put("username", username)
            put("password", password)
        },
    ).let { resp ->
        resp.jsonObject.let {
            BffAuth(
                token = it.str("token"),
                role = it.str("role"),
                displayName = it.str("display_name"),
            )
        }
    }

    suspend fun join(inviteCode: String, displayName: String): BffAuth = post(
        path = "/auth/join",
        body = buildJsonObject {
            put("invite_code", inviteCode)
            put("display_name", displayName)
        },
    ).let { resp ->
        resp.jsonObject.let {
            BffAuth(
                token = it.str("token"),
                role = it.str("role"),
                displayName = it.str("display_name"),
            )
        }
    }

    suspend fun getProfile(token: String): Map<String, kotlinx.serialization.json.JsonElement> =
        get("/family/profile", token).jsonObject

    suspend fun putProfile(token: String, profileJson: String) {
        request(
            Request.Builder()
                .url(url("/family/profile"))
                .header("Authorization", "Bearer $token")
                .put(profileJson.toRequestBody("application/json".toMediaType()))
        )
    }

    suspend fun getPersona(token: String): BffPersona =
        json.decodeFromString(get("/family/persona", token).toString())

    suspend fun putPersona(token: String, persona: BffPersona) = post(
        path = "/family/persona",
        token = token,
        body = json.parseToJsonElement(json.encodeToString(persona)).jsonObject,
    ).let { }

    suspend fun putKey(token: String, key: BffKeyMasked) = post(
        path = "/family/keys",
        token = token,
        body = buildJsonObject {
            put("provider", key.provider)
            put("base_url", key.base_url)
            put("model", key.model)
            put("api_key", key.api_key_masked) // 复用字段名传真实 Key
        },
    ).let { }

    suspend fun getKeys(token: String): List<BffKeyMasked> =
        json.decodeFromString(get("/family/keys", token).toString())

    suspend fun getMembers(token: String): List<BffMember> =
        json.decodeFromString(get("/family/members", token).toString())

    suspend fun createInvite(token: String): String =
        post("/auth/invite", token = token, body = buildJsonObject {}).let {
            it.jsonObject.str("invite_code")
        }

    suspend fun getHistory(token: String, limit: Int = 50, offset: Int = 0): BffHistoryPage {
        val resp = get("/history?limit=$limit&offset=$offset", token)
        return json.decodeFromString(resp.toString())
    }

    // ---------- SSE 对话 ----------

    /**
     * 文本对话（App 本地 ASR 完成后的主路径）。
     * @return 服务端完整回复文本
     */
    suspend fun chatText(
        token: String,
        text: String,
        onEvent: (BffEvent) -> Unit,
    ): String {
        val body = buildJsonObject { put("text", text) }.toString()
        return sseChat(
            request = Request.Builder()
                .url(url("/chat/text"))
                .header("Authorization", "Bearer $token")
                .post(body.toRequestBody("application/json".toMediaType()))
                .build(),
            onEvent = onEvent,
        )
    }

    /**
     * 音频兜底对话（本地识别失败时上传录音，云端再听一遍）。
     * @param wavBytes App 录制的 WAV 音频
     */
    suspend fun chatAudio(
        token: String,
        wavBytes: ByteArray,
        onEvent: (BffEvent) -> Unit,
    ): String {
        // FastAPI UploadFile 要求 multipart/form-data，字段名 file
        val body = MultipartBody.Builder()
            .setType(MultipartBody.FORM)
            .addFormDataPart(
                "file", "audio.wav",
                wavBytes.toRequestBody("audio/wav".toMediaType()),
            )
            .build()
        return sseChat(
            request = Request.Builder()
                .url(url("/chat/audio"))
                .header("Authorization", "Bearer $token")
                .post(body)
                .build(),
            onEvent = onEvent,
        )
    }

    private suspend fun sseChat(request: Request, onEvent: (BffEvent) -> Unit): String =
        withContext(Dispatchers.IO) {
            client.newCall(request).execute().use { response ->
                if (!response.isSuccessful) {
                    throw IOException("服务器 HTTP ${response.code}")
                }
                val source = response.body?.source() ?: throw IOException("空响应")
                var fullReply = ""
                while (!source.exhausted()) {
                    currentCoroutineContext().ensureActive()
                    val line = source.readUtf8Line() ?: break
                    if (!line.startsWith("data:")) continue // 跳过心跳 ": ping"
                    val data = line.removePrefix("data:").trim()
                    if (data.isEmpty()) continue
                    val obj = runCatching { json.parseToJsonElement(data).jsonObject }
                        .getOrNull() ?: continue
                    when (obj.str("type")) {
                        "meta" -> onEvent(BffEvent.Meta(obj["tts"]?.jsonPrimitive?.booleanOrNull ?: false))
                        "asr" -> onEvent(BffEvent.Asr(obj.str("text")))
                        "reply" -> onEvent(BffEvent.Reply(obj.str("text")))
                        "audio" -> runCatching {
                            android.util.Base64.decode(
                                obj.str("data"), android.util.Base64.DEFAULT,
                            )
                        }.getOrNull()?.let { onEvent(BffEvent.Audio(it)) }
                        "done" -> {
                            fullReply = obj.str("reply")
                            onEvent(BffEvent.Done(fullReply))
                        }
                        "error" -> onEvent(BffEvent.Error(obj.str("message")))
                    }
                }
                fullReply
            }
        }

    // ---------- 内部工具 ----------

    private fun url(path: String) = baseUrl.trimEnd('/') + path

    private suspend fun request(builder: Request.Builder): String =
        withContext(Dispatchers.IO) {
            client.newCall(builder.build()).execute().use { resp ->
                val text = resp.body?.string().orEmpty()
                if (!resp.isSuccessful) {
                    throw IOException("HTTP ${resp.code}: ${text.take(120)}")
                }
                text
            }
        }

    private suspend fun get(path: String, token: String): kotlinx.serialization.json.JsonElement =
        request(
            Request.Builder().url(url(path)).header("Authorization", "Bearer $token").get()
        ).let { json.parseToJsonElement(it) }

    private suspend fun post(
        path: String,
        token: String? = null,
        body: JsonObject,
    ): kotlinx.serialization.json.JsonElement = request(
        Request.Builder()
            .url(url(path))
            .apply { token?.let { header("Authorization", "Bearer $it") } }
            .post(body.toString().toRequestBody("application/json".toMediaType()))
    ).let { json.parseToJsonElement(it) }

    private fun JsonObject.str(key: String): String =
        this[key]?.jsonPrimitive?.contentOrNull ?: ""
}
