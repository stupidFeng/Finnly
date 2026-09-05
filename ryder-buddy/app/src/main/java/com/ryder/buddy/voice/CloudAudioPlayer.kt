package com.ryder.buddy.voice

import android.content.Context
import android.media.MediaPlayer
import android.os.Handler
import android.os.Looper
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import java.io.File
import java.util.concurrent.atomic.AtomicInteger

/**
 * 云端音频播放器：播放服务端合成好的莱德音色 MP3（句子级队列）。
 * 与本地 AndroidTtsClient 并存——meta.tts=true 用这个，false 用本地 TTS。
 *
 * SSE 事件在 IO 线程回调，而 MediaPlayer 需要有 Looper 的线程——
 * 所有操作统一 post 到主线程执行。
 */
class CloudAudioPlayer(private val context: Context) {

    private val mainHandler = Handler(Looper.getMainLooper())

    private val _busy = MutableStateFlow(false)
    val busy: StateFlow<Boolean> = _busy.asStateFlow()

    private var player: MediaPlayer? = null
    private val pending = ArrayDeque<File>()
    private val active = AtomicInteger(0)
    private var fileSeq = 0

    /** 把一段 MP3 加入播放队列（SSE audio 事件到达即调，按句排队） */
    fun enqueue(mp3: ByteArray) {
        val file = File(context.cacheDir, "ryder-tts-${fileSeq++}.mp3")
        file.writeBytes(mp3)
        mainHandler.post {
            synchronized(pending) { pending.addLast(file) }
            playNextIfIdle()
        }
    }

    private fun playNextIfIdle() {
        val next: File = synchronized(pending) { pending.removeFirstOrNull() } ?: return
        if (active.get() > 0) {
            // 已在播则放回（由 onCompletion 驱动）
            synchronized(pending) { pending.addFirst(next) }
            return
        }
        active.incrementAndGet()
        _busy.value = true
        try {
            val p = MediaPlayer()
            player = p
            p.setDataSource(next.absolutePath)
            p.setOnCompletionListener {
                it.release()
                if (player === it) player = null
                next.delete()
                settle()
            }
            p.setOnErrorListener { mp, _, _ ->
                mp.release()
                if (player === mp) player = null
                next.delete()
                settle()
                true
            }
            p.prepare()
            p.start()
        } catch (_: Exception) {
            next.delete()
            settle()
        }
    }

    private fun settle() {
        if (active.decrementAndGet() <= 0) {
            active.set(0)
            _busy.value = false
        }
        playNextIfIdle() // 队列里还有就继续
    }

    /** 立即清空队列并停止（孩子打断莱德时调用） */
    fun stop() {
        mainHandler.post {
            synchronized(pending) {
                pending.forEach { it.delete() }
                pending.clear()
            }
            player?.let { p ->
                runCatching { p.stop() }
                runCatching { p.release() }
            }
            player = null
            active.set(0)
            _busy.value = false
        }
    }
}
