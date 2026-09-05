package com.ryder.buddy.voice

import android.annotation.SuppressLint
import android.media.AudioFormat
import android.media.AudioRecord
import android.media.MediaRecorder

/**
 * 并行录音器：本地 ASR 聆听的同时把孩子的声音录成 WAV。
 * 本地识别失败时，这份录音直接上传后端走云端 ASR 兜底（「再听一遍」）。
 *
 * 与 SpeechRecognizer 并行开麦在部分设备可能失败——失败不致命，
 * 拿不到录音就只报本地错误，不影响主流程。
 */
class AudioRecorder {

    private var thread: Thread? = null
    private var record: AudioRecord? = null
    @Volatile
    private var running = false

    private val sampleRate = 16000

    /** 是否拿到了可用录音（stop 后有效） */
    var hasAudio: Boolean = false
        private set

    private var wavBytes: ByteArray = ByteArray(0)

    @SuppressLint("MissingPermission") // 调用方已确保 RECORD_AUDIO 权限
    fun start(): Boolean {
        if (running) return true
        hasAudio = false
        wavBytes = ByteArray(0)

        val minBuf = AudioRecord.getMinBufferSize(
            sampleRate, AudioFormat.CHANNEL_IN_MONO, AudioFormat.ENCODING_PCM_16BIT,
        )
        if (minBuf <= 0) return false

        val r = try {
            AudioRecord(
                MediaRecorder.AudioSource.MIC,
                sampleRate,
                AudioFormat.CHANNEL_IN_MONO,
                AudioFormat.ENCODING_PCM_16BIT,
                minBuf * 2,
            )
        } catch (_: Exception) {
            return false
        }
        if (r.state != AudioRecord.STATE_INITIALIZED) {
            r.release()
            return false
        }

        val buffer = ByteArray(minBuf)
        val chunks = ArrayList<ByteArray>()
        running = true
        record = r
        r.startRecording()

        thread = Thread {
            try {
                while (running) {
                    val n = r.read(buffer, 0, buffer.size)
                    if (n > 0) chunks.add(buffer.copyOf(n))
                }
            } catch (_: Exception) {
                // 被打断或设备冲突，保留已录到的部分
            }
            if (chunks.isNotEmpty()) {
                wavBytes = wav(chunks)
                hasAudio = wavBytes.size > 8000 // 约 0.25 秒以下视为无效
            }
        }.also { it.start() }
        return true
    }

    /** 停止并取回 WAV；未录到返回 null */
    fun stop(): ByteArray? {
        running = false
        runCatching { thread?.join(1000) }
        thread = null
        runCatching { record?.stop() }
        runCatching { record?.release() }
        record = null
        return if (hasAudio) wavBytes else null
    }

    /** 丢弃录音（识别成功就不需要兜底了） */
    fun discard() {
        running = false
        runCatching { thread?.join(500) }
        thread = null
        runCatching { record?.stop() }
        runCatching { record?.release() }
        record = null
        wavBytes = ByteArray(0)
        hasAudio = false
    }

    /** PCM 块拼成带头的 WAV */
    private fun wav(chunks: List<ByteArray>): ByteArray {
        var dataLen = 0
        chunks.forEach { dataLen += it.size }
        val header = ByteArray(44)
        fun le32(pos: Int, v: Int) {
            header[pos] = (v and 0xFF).toByte()
            header[pos + 1] = ((v shr 8) and 0xFF).toByte()
            header[pos + 2] = ((v shr 16) and 0xFF).toByte()
            header[pos + 3] = ((v shr 24) and 0xFF).toByte()
        }
        fun le16(pos: Int, v: Int) {
            header[pos] = (v and 0xFF).toByte()
            header[pos + 1] = ((v shr 8) and 0xFF).toByte()
        }
        val byteRate = sampleRate * 2 // 单声道 16bit
        System.arraycopy("RIFF".toByteArray(), 0, header, 0, 4)
        le32(4, 36 + dataLen)
        System.arraycopy("WAVE".toByteArray(), 0, header, 8, 4)
        System.arraycopy("fmt ".toByteArray(), 0, header, 12, 4)
        le32(16, 16)
        le16(20, 1) // PCM
        le16(22, 1) // 单声道
        le32(24, sampleRate)
        le32(28, byteRate)
        le16(32, 2)
        le16(34, 16)
        System.arraycopy("data".toByteArray(), 0, header, 36, 4)
        le32(40, dataLen)

        val out = ByteArray(44 + dataLen)
        System.arraycopy(header, 0, out, 0, 44)
        var pos = 44
        chunks.forEach { c ->
            System.arraycopy(c, 0, out, pos, c.size)
            pos += c.size
        }
        return out
    }
}
