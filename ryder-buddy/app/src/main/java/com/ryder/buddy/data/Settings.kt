package com.ryder.buddy.data

import android.content.Context
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.stringPreferencesKey
import androidx.datastore.preferences.preferencesDataStore
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.map
import kotlinx.serialization.Serializable
import kotlinx.serialization.decodeFromString
import kotlinx.serialization.encodeToString
import kotlinx.serialization.json.Json

/**
 * 家长注入的记忆档案。
 * 每次对话前由 PersonaPromptBuilder 拼进 system prompt，让莱德"认识"孩子。
 */
@Serializable
data class MemoryProfile(
    val nickname: String = "",          // 小名，如"糖糖"
    val birthDate: String = "",         // 出生日期 yyyy-MM-dd，自动计算年龄，回答永远是"活的"
    val heightWeight: String = "",      // 如 92cm / 13.5kg
    val likes: String = "",             // 喜欢的玩具 / 食物 / 角色
    val fears: String = "",             // 害怕的东西，如打雷、吸尘器
    val routine: String = "",           // 作息，如 21:00 睡觉
    val familyTitles: String = "",      // 家人称呼，如 爸爸、妈妈、奶奶
    val comfortKit: List<String> = emptyList(), // 安抚锦囊：哭闹时莱德优先使用的方法
)

/** 大模型接入设置（OpenAI 兼容协议，豆包 / GLM / 通义均可） */
@Serializable
data class LlmSettings(
    val useStub: Boolean = true,        // 离线演示模式：无需 API Key，使用内置应答
    val baseUrl: String = "https://ark.cn-beijing.volces.com/api/v3", // 火山方舟示例
    val model: String = "",             // 模型 ID
    val apiKey: String = "",
)

private val Context.dataStore by preferencesDataStore(name = "ryder_settings")

class SettingsRepository(private val context: Context) {

    private val json = Json {
        ignoreUnknownKeys = true
        encodeDefaults = true
    }

    val profile: Flow<MemoryProfile> = context.dataStore.data.map { prefs ->
        prefs[KEY_PROFILE]?.let { decode(it) } ?: MemoryProfile()
    }

    val llmSettings: Flow<LlmSettings> = context.dataStore.data.map { prefs ->
        prefs[KEY_LLM]?.let { decode(it) } ?: LlmSettings()
    }

    suspend fun saveProfile(profile: MemoryProfile) {
        context.dataStore.edit { it[KEY_PROFILE] = json.encodeToString(profile) }
    }

    suspend fun saveLlmSettings(settings: LlmSettings) {
        context.dataStore.edit { it[KEY_LLM] = json.encodeToString(settings) }
    }

    private inline fun <reified T> decode(raw: String): T? =
        runCatching { json.decodeFromString<T>(raw) }.getOrNull()

    companion object {
        private val KEY_PROFILE = stringPreferencesKey("profile_json")
        private val KEY_LLM = stringPreferencesKey("llm_json")
    }
}
