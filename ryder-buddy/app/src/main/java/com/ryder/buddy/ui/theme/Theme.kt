package com.ryder.buddy.ui.theme

import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color

// 莱德队服蓝为主色，明亮、幼儿友好；固定浅色主题，夜晚使用交给后续"哄睡模式"调暗
private val LightColors = lightColorScheme(
    primary = Color(0xFF2E7CF6),
    onPrimary = Color.White,
    primaryContainer = Color(0xFFD9E8FF),
    onPrimaryContainer = Color(0xFF0B3B75),
    secondary = Color(0xFF2FA768),
    background = Color(0xFFEAF3FF),
    onBackground = Color(0xFF16233A),
    surface = Color.White,
    onSurface = Color(0xFF16233A),
    surfaceVariant = Color(0xFFE4ECF8),
    onSurfaceVariant = Color(0xFF48586F),
)

@Composable
fun RyderBuddyTheme(
    darkTheme: Boolean = isSystemInDarkTheme(),
    content: @Composable () -> Unit,
) {
    // 幼儿场景始终用浅色，darkTheme 参数留给以后做"哄睡模式"夜间配色
    MaterialTheme(colorScheme = LightColors, content = content)
}
