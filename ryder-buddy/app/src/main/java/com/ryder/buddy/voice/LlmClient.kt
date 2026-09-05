package com.ryder.buddy.voice

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.currentCoroutineContext
import kotlinx.coroutines.delay
import kotlinx.coroutines.ensureActive
import kotlinx.coroutines.withContext
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.addJsonObject
import kotlinx.serialization.json.buildJsonArray
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.jsonArray
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import kotlinx.serialization.json.put
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import java.io.IOException
import java.util.concurrent.TimeUnit

@Serializable
data class ChatMessage(val role: String, val content: String)

/**
 * 大模型抽象。默认提供两个实现：
 *  - StubLlmClient：离线演示，无需 API Key，关键词匹配出莱德风格的固定应答
 *  - OpenAiCompatibleLlmClient：OpenAI 兼容流式接口（豆包方舟 / GLM / 通义均支持）
 */
interface LlmClient {
    /** 流式对话。history 已包含本次的用户消息；返回完整回复文本 */
    suspend fun chatStream(
        systemPrompt: String,
        history: List<ChatMessage>,
        onDelta: (String) -> Unit,
    ): String
}

/** 离线演示大脑：先跑通整条语音链路，接入云端前给女儿玩 */
class StubLlmClient : LlmClient {

    override suspend fun chatStream(
        systemPrompt: String,
        history: List<ChatMessage>,
        onDelta: (String) -> Unit,
    ): String {
        val userText = history.lastOrNull { it.role == "user" }?.content.orEmpty()
        val reply = pickReply(userText)
        // 按 4 字一块模拟流式输出，方便验证"边生成边朗读"
        reply.chunked(4).forEach { chunk ->
            onDelta(chunk)
            delay(40)
        }
        return reply
    }

    private fun pickReply(userText: String): String = when {
        userText.contains("怕") || userText.contains("哭") || userText.contains("噩梦") ->
            "我知道你有点难过。莱德陪着你呢！抱抱你最喜欢的小玩偶，好不好？"
        userText.contains("故事") || userText.contains("讲") ->
            "好呀！莱德讲个小故事。从前有只勇敢的小狗狗，帮迷路的小猫咪找到了家。小狗狗说，没有困难的任务，只有勇敢的狗狗！"
        userText.contains("唱歌") || userText.contains("歌") ->
            "一闪一闪亮晶晶，满天都是小星星！莱德唱得好不好听呀？"
        userText.contains("睡觉") || userText.contains("晚安") ->
            "晚安啦！闭上眼睛，莱德和狗狗们会守护你的梦！"
        userText.contains("汪汪队") || userText.contains("莱德") ->
            "没错！我就是莱德队长！毛毛、阿奇它们都在冒险湾等你哦！"
        userText.contains("你好") || userText.contains("嗨") || userText.contains("哈喽") ->
            "你好呀！我是莱德队长！今天想和莱德做什么呀？"
        else -> listOf(
            "哇！你说得真棒！能再告诉莱德一件今天开心的事吗？",
            "收到！莱德队长明白啦！你真是勇敢的小队员！",
        ).random()
    }
}

/**
 * OpenAI 兼容的流式客户端。SSE 逐行解析，token 一到就回调 onDelta。
 * 豆包（火山方舟）、GLM、通义都提供兼容端点，改 baseUrl + model 即可切换。
 */
class OpenAiCompatibleLlmClient(
    private val baseUrl: String,
    private val apiKey: String,
    private val model: String,
) : LlmClient {

    private val client = OkHttpClient.Builder()
        .connectTimeout(10, TimeUnit.SECONDS)
        .readTimeout(60, TimeUnit.SECONDS)
        .build()

    private val json = Json { ignoreUnknownKeys = true }

    override suspend fun chatStream(
        systemPrompt: String,
        history: List<ChatMessage>,
        onDelta: (String) -> Unit,
    ): String = withContext(Dispatchers.IO) {
        val messages = buildJsonArray {
            addJsonObject {
                put("role", "system")
                put("content", systemPrompt)
            }
            history.forEach { m ->
                addJsonObject {
                    put("role", m.role)
                    put("content", m.content)
                }
            }
        }
        val body = buildJsonObject {
            put("model", model)
            put("messages", messages)
            put("stream", true)
            put("temperature", 0.8)
            put("max_tokens", 200)
        }
        val request = Request.Builder()
            .url(baseUrl.trimEnd('/') + "/chat/completions")
            .header("Authorization", "Bearer $apiKey")
            .post(body.toString().toRequestBody("application/json".toMediaType()))
            .build()

        client.newCall(request).execute().use { response ->
            if (!response.isSuccessful) {
                throw IOException("LLM HTTP ${response.code}: ${response.body?.string()?.take(200)}")
            }
            val source = response.body?.source() ?: throw IOException("empty body")
            val full = StringBuilder()
            while (!source.exhausted()) {
                currentCoroutineContext().ensureActive()
                val line = source.readUtf8Line() ?: break
                if (!line.startsWith("data:")) continue
                val data = line.removePrefix("data:").trim()
                if (data.isEmpty() || data == "[DONE]") continue
                val delta = runCatching {
                    json.parseToJsonElement(data).jsonObject["choices"]?.jsonArray
                        ?.firstOrNull()?.jsonObject?.get("delta")?.jsonObject
                        ?.get("content")?.jsonPrimitive?.content
                }.getOrNull() ?: continue
                if (delta.isNotEmpty()) {
                    full.append(delta)
                    onDelta(delta)
                }
            }
            full.toString()
        }
    }
}
