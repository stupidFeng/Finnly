package com.ryder.buddy.voice

/**
 * 语音对话管线：LLM 边生成、句子边落 TTS 队列。
 *
 * 幼儿等不了长回答——流式 + 按句切分是低延迟的关键：
 * 第一句话生成完就开始朗读，后面的句子在播放中继续生成。
 */
class VoicePipeline(
    private val llm: LlmClient,
    private val tts: TtsClient,
) {

    /**
     * 处理一轮对话。history 需已包含本次用户消息。
     * @param onReplyStarted 第一句话送进 TTS 时回调（UI 切换到"莱德在说话"状态）
     * @return 完整回复文本
     */
    suspend fun respond(
        systemPrompt: String,
        history: List<ChatMessage>,
        onReplyStarted: () -> Unit,
    ): String {
        val pending = StringBuilder()
        var started = false

        fun dispatch(sentence: String) {
            val cleaned = sentence.replace("*", "").replace("#", " ").trim()
            if (cleaned.isBlank()) return
            if (!started) {
                started = true
                onReplyStarted()
            }
            tts.speak(cleaned)
        }

        // 把缓冲区里完整的句子（以 。！？ 等结尾）逐句送进 TTS
        fun drain(flushAll: Boolean) {
            while (true) {
                val text = pending.toString()
                val idx = text.indexOfAny(SENTENCE_END)
                if (idx < 0) break
                dispatch(text.substring(0, idx + 1))
                pending.delete(0, idx + 1)
            }
            if (flushAll && pending.isNotBlank()) {
                dispatch(pending.toString())
                pending.clear()
            }
        }

        val full = llm.chatStream(systemPrompt, history) { delta ->
            pending.append(delta)
            drain(flushAll = false)
        }
        drain(flushAll = true)
        return full
    }

    companion object {
        private val SENTENCE_END = charArrayOf('。', '！', '？', '!', '?', '；', ';', '\n')
    }
}
