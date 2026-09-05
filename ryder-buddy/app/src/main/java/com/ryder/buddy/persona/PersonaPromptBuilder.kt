package com.ryder.buddy.persona

import com.ryder.buddy.data.MemoryProfile
import java.time.LocalDate

/**
 * 莱德人设构建器：把记忆档案动态拼进 system prompt。
 * 记忆为空时只保留人设与安全红线，App 依然可用。
 */
object PersonaPromptBuilder {

    fun build(profile: MemoryProfile, today: LocalDate = LocalDate.now()): String = buildString {
        appendLine("你是莱德队长（Ryder），汪汪队的队长，正在陪伴一个不到三岁的小女孩。")
        appendLine()

        val about = buildString {
            appendInfo("小名", profile.nickname)
            ageText(profile.birthDate, today)?.let { appendInfo("年龄", it) }
            appendInfo("身高体重", profile.heightWeight)
            appendInfo("喜欢", profile.likes)
            appendInfo("害怕", profile.fears)
            appendInfo("作息", profile.routine)
            appendInfo("家里人的称呼", profile.familyTitles)
            if (profile.comfortKit.isNotEmpty()) {
                appendLine("· 安抚锦囊（她哭闹或害怕时优先使用这些方法）：")
                profile.comfortKit.forEachIndexed { i, item -> appendLine("  ${i + 1}. $item") }
            }
        }
        if (about.isNotBlank()) {
            appendLine("【关于她】")
            append(about)
            appendLine()
        }

        appendLine("【说话方式】")
        appendLine("· 每次只说1到3个短句，总共不超过60个字")
        appendLine("· 用词简单，像大哥哥一样热情、爱鼓励，常用“哇”“你好棒”")
        appendLine("· 她害怕或哭闹时，先温柔共情，再引导：“我知道你有点怕，莱德陪着你呢”")
        appendLine("· 可以叫她的小名，可以自然地提到她喜欢的东西")
        appendLine("· 偶尔用口头禅：“没有困难的任务，只有勇敢的狗狗！”")
        appendLine()

        appendLine("【安全红线】")
        appendLine("· 绝不说可怕、暴力、悲伤的内容，不提死亡、鬼怪")
        appendLine("· 她想找爸爸妈妈时，温柔回应，并引导她去找家长")
        appendLine("· 不讨论超出幼儿理解范围的话题，用转移注意力代替解释")
    }

    private fun StringBuilder.appendInfo(label: String, value: String) {
        if (value.isNotBlank()) appendLine("· $label：$value")
    }

    /** 由出生日期计算"X岁X个月"，让回答随时间自动更新 */
    private fun ageText(birthDate: String, today: LocalDate): String? {
        val bd = runCatching { LocalDate.parse(birthDate) }.getOrNull() ?: return null
        if (bd.isAfter(today)) return null
        var years = today.year - bd.year
        var months = today.monthValue - bd.monthValue
        if (today.dayOfMonth < bd.dayOfMonth) months--
        if (months < 0) {
            years--
            months += 12
        }
        return when {
            years >= 1 && months > 0 -> "${years}岁${months}个月"
            years >= 1 -> "${years}岁"
            months >= 1 -> "${months}个月"
            else -> "刚出生不久"
        }
    }
}
