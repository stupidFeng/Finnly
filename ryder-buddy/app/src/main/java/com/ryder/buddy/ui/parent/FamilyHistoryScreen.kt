package com.ryder.buddy.ui.parent

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.Card
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.ryder.buddy.MainViewModel
import com.ryder.buddy.voice.BffHistoryPage

/** 父亲专用：全家对话记录回放（按成员区分是谁陪聊的） */
@Composable
fun FamilyHistoryScreen(vm: MainViewModel, onBack: () -> Unit) {
    var page by remember { mutableStateOf<BffHistoryPage?>(null) }
    var loading by remember { mutableStateOf(true) }

    fun load(offset: Int = 0) {
        loading = true
        vm.loadHistory(limit = 50, offset = offset) { result ->
            page = result
            loading = false
        }
    }

    LaunchedEffect(Unit) { load(0) }

    Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        Row(
            Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Text("全家对话记录", style = MaterialTheme.typography.headlineSmall)
            TextButton(onClick = onBack) { Text("返回") }
        }

        val p = page
        when {
            loading -> Row(
                Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.Center,
            ) { CircularProgressIndicator() }

            p == null || p.items.isEmpty() -> Text("还没有对话记录")

            else -> {
                Text(
                    "共 ${p.total} 条 · 显示最新 ${p.items.size} 条",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
                LazyColumn(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    items(p.items) { item ->
                        Card {
                            Column(Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                                Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                                    Text(item.member_name, fontWeight = FontWeight.Bold,
                                        color = MaterialTheme.colorScheme.primary)
                                    Text(
                                        formatTime(item.created_at),
                                        style = MaterialTheme.typography.bodySmall,
                                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                                    )
                                }
                                Text("孩子说：${item.user_text}",
                                    style = MaterialTheme.typography.bodyMedium)
                                Text("莱德说：${item.reply_text}",
                                    style = MaterialTheme.typography.bodyMedium)
                                if (item.source == "audio") {
                                    Text(
                                        "（云端重听）",
                                        style = MaterialTheme.typography.bodySmall,
                                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                                    )
                                }
                            }
                        }
                    }
                }
            }
        }

        OutlinedButton(
            onClick = { load(0) },
            modifier = Modifier.fillMaxWidth(),
        ) { Text("刷新") }
        Spacer(Modifier.height(24.dp))
    }
}

/** 后端返回 UTC ISO 时间，转成友好显示（家长看相对时间足够） */
private fun formatTime(iso: String): String = runCatching {
    val parsed = java.time.Instant.parse(iso)
    val shanghai = java.time.ZoneId.of("Asia/Shanghai")
    val dt = java.time.LocalDateTime.ofInstant(parsed, shanghai)
    "${dt.monthValue}/${dt.dayOfMonth} ${dt.hour}:${"%02d".format(dt.minute)}"
}.getOrDefault(iso.take(16))
