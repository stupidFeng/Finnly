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
 * 家长注入的记忆档案（本地缓存快照）。
 * 权威版本在家庭后端：父亲改一次，全家 App 同步；
 * 后端不可达时用这份缓存兜底（离线演示模式）。
 */
@Serializable
data class MemoryProfile(
    val nickname: String = "",          // 小名，如"糖糖"
    val birthDate: String = "",         // 出生日期 yyyy-MM-dd，服务端自动算年龄
    val heightWeight: String = "",      // 如 92cm / 13.5kg
    val likes: String = "",             // 喜欢的玩具 / 食物 / 角色
    val fears: String = "",             // 害怕的东西，如打雷、吸尘器
    val routine: String = "",           // 作息，如 21:00 睡觉
    val familyTitles: String = "",      // 家人称呼，如 爸爸、妈妈、奶奶
    val comfortKit: List<String> = emptyList(), // 安抚锦囊：哭闹时莱德优先使用的方法
)

/** 家庭后端连接信息：null / 空即离线演示模式 */
@Serializable
data class ServerConfig(
    val baseUrl: String = "",   // 如 https://ryder.example.com
    val token: String = "",     // JWT（父亲或成员）
    val role: String = "",      // father / member
    val displayName: String = "",
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

    val serverConfig: Flow<ServerConfig?> = context.dataStore.data.map { prefs ->
        prefs[KEY_SERVER]?.let { decode<ServerConfig>(it) }
    }

    suspend fun saveProfile(profile: MemoryProfile) {
        context.dataStore.edit { it[KEY_PROFILE] = json.encodeToString(profile) }
    }

    suspend fun saveServerConfig(config: ServerConfig) {
        context.dataStore.edit { it[KEY_SERVER] = json.encodeToString(config) }
    }

    suspend fun clearServerConfig() {
        context.dataStore.edit { it.remove(KEY_SERVER) }
    }

    private inline fun <reified T> decode(raw: String): T? =
        runCatching { json.decodeFromString<T>(raw) }.getOrNull()

    companion object {
        private val KEY_PROFILE = stringPreferencesKey("profile_json")
        private val KEY_SERVER = stringPreferencesKey("server_json")
    }
}
