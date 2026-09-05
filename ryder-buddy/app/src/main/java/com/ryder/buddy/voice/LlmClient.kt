package com.ryder.buddy.voice

import kotlinx.serialization.Serializable
import kotlinx.coroutines.delay

@Serializable
data class ChatMessage(val role: String, val content: String)

/**
 * 离线演示大脑：不连任何服务器，关键词匹配出莱德风格应答。
 * 用于：服务器未配置时先跑通整条语音链路，给女儿试玩。
 */
interface LlmClient {
    /** 流式对话。history 已包含本次的用户消息；返回完整回复文本 */
    suspend fun chatStream(
        systemPrompt: String,
        history: List<ChatMessage>,
        onDelta: (String) -> Unit,
    ): String
}

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
