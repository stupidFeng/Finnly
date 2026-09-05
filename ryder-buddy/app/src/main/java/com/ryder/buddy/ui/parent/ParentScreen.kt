package com.ryder.buddy.ui.parent

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.SegmentedButton
import androidx.compose.material3.SegmentedButtonDefaults
import androidx.compose.material3.SingleChoiceSegmentedButtonRow
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.ryder.buddy.MainViewModel
import com.ryder.buddy.data.MemoryProfile
import com.ryder.buddy.voice.BffKeyMasked
import com.ryder.buddy.voice.BffPersona

/**
 * 家长面板：
 *  - 未连接服务器：本地记忆编辑（离线演示模式）
 *  - 成员登录：只读查看
 *  - 父亲登录：记忆/人设/Key/邀请码/成员/对话记录 全功能
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ParentScreen(
    vm: MainViewModel,
    onOpenHistory: () -> Unit,
    onBack: () -> Unit,
) {
    val serverConfig by vm.serverConfig.collectAsState()
    val scroll = rememberScrollState()

    Column(
        modifier = Modifier
            .fillMaxWidth()
            .verticalScroll(scroll)
            .padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(16.dp),
    ) {
        Text("家长面板", style = MaterialTheme.typography.headlineSmall)

        val config = serverConfig
        if (config == null || config.baseUrl.isBlank()) {
            // ---------- 未连接：服务器连接 + 本地离线编辑 ----------
            ServerConnectSection(vm)
            LocalProfileSection(vm)
        } else if (config.role == "father") {
            // ---------- 父亲：全功能 ----------
            ConnectedHeader(vm, config.displayName, isAdmin = true)
            MemoryProfileSection(vm)
            PersonaSection(vm)
            ProviderKeysSection(vm)
            InviteSection(vm)
            Button(onClick = onOpenHistory, modifier = Modifier.fillMaxWidth()) {
                Text("查看全家对话记录")
            }
        } else {
            // ---------- 成员：只读 ----------
            ConnectedHeader(vm, config.displayName, isAdmin = false)
            Text(
                "记忆档案由爸爸统一管理，这里展示当前生效的内容。",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            ReadonlyProfileSection(vm)
        }

        OutlinedButton(onClick = onBack, modifier = Modifier.fillMaxWidth()) {
            Text("返回孩子页面")
        }
        Spacer(Modifier.height(24.dp))
    }
}

// ---------- 服务器连接 ----------

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun ServerConnectSection(vm: MainViewModel) {
    Card(colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceVariant)) {
        Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
            Text("连接家庭服务器", fontWeight = FontWeight.Bold)

            var baseUrl by rememberSaveable { mutableStateOf("http://") }
            OutlinedTextField(
                value = baseUrl,
                onValueChange = { baseUrl = it },
                label = { Text("服务器地址") },
                modifier = Modifier.fillMaxWidth(),
                singleLine = true,
            )

            var mode by rememberSaveable { mutableStateOf(0) } // 0=爸爸登录 1=家人邀请码
            SingleChoiceSegmentedButtonRow(Modifier.fillMaxWidth()) {
                SegmentedButton(
                    selected = mode == 0,
                    onClick = { mode = 0 },
                    shape = SegmentedButtonDefaults.itemShape(0, 2),
                ) { Text("爸爸登录") }
                SegmentedButton(
                    selected = mode == 1,
                    onClick = { mode = 1 },
                    shape = SegmentedButtonDefaults.itemShape(1, 2),
                ) { Text("家人加入") }
            }

            var username by rememberSaveable { mutableStateOf("") }
            var password by rememberSaveable { mutableStateOf("") }
            var inviteCode by rememberSaveable { mutableStateOf("") }
            var displayName by rememberSaveable { mutableStateOf("") }
            var error by remember { mutableStateOf<String?>(null) }
            var busy by remember { mutableStateOf(false) }

            if (mode == 0) {
                OutlinedTextField(
                    value = username, onValueChange = { username = it },
                    label = { Text("用户名") },
                    modifier = Modifier.fillMaxWidth(), singleLine = true,
                )
                OutlinedTextField(
                    value = password, onValueChange = { password = it },
                    label = { Text("密码") },
                    modifier = Modifier.fillMaxWidth(), singleLine = true,
                )
            } else {
                OutlinedTextField(
                    value = inviteCode, onValueChange = { inviteCode = it },
                    label = { Text("邀请码（爸爸生成）") },
                    modifier = Modifier.fillMaxWidth(), singleLine = true,
                )
                OutlinedTextField(
                    value = displayName, onValueChange = { displayName = it },
                    label = { Text("我是谁（如：阿婆）") },
                    modifier = Modifier.fillMaxWidth(), singleLine = true,
                )
            }

            error?.let {
                Text(it, color = MaterialTheme.colorScheme.error,
                    style = MaterialTheme.typography.bodySmall)
            }

            Button(
                onClick = {
                    busy = true
                    error = null
                    val url = baseUrl.trim()
                    if (mode == 0) {
                        vm.login(url, username, password) { err ->
                            busy = false
                            error = err?.let { "登录失败：$it" }
                        }
                    } else {
                        vm.join(url, inviteCode, displayName.ifBlank { "家人" }) { err ->
                            busy = false
                            error = err?.let { "加入失败：$it" }
                        }
                    }
                },
                enabled = !busy && baseUrl.startsWith("http"),
                modifier = Modifier.fillMaxWidth(),
            ) {
                if (busy) CircularProgressIndicator(Modifier.height(18.dp)) else Text("连接")
            }

            Text(
                "阿婆、妈妈等家人用「家人加入」，凭爸爸发的邀请码登录，无需密码。",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
    }
}

@Composable
private fun ConnectedHeader(vm: MainViewModel, displayName: String, isAdmin: Boolean) {
    Card(colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.primaryContainer)) {
        Row(
            Modifier
                .fillMaxWidth()
                .padding(16.dp),
            horizontalArrangement = Arrangement.SpaceBetween,
        ) {
            Column {
                Text(displayName, fontWeight = FontWeight.Bold)
                Text(
                    if (isAdmin) "父亲 · 管理员" else "家庭成员",
                    style = MaterialTheme.typography.bodySmall,
                )
            }
            TextButton(onClick = { vm.logout() }) { Text("退出登录") }
        }
    }
}

// ---------- 记忆档案 ----------

@Composable
private fun MemoryProfileSection(vm: MainViewModel) {
    val profile by vm.profile.collectAsState()
    val p = profile ?: return

    Card {
        Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
            Text("记忆档案（保存到服务器，全家生效）", fontWeight = FontWeight.Bold)
            ProfileForm(initial = p) { updated ->
                vm.saveProfileRemote(updated) { }
            }
        }
    }
}

@Composable
private fun LocalProfileSection(vm: MainViewModel) {
    val profile by vm.profile.collectAsState()
    val p = profile ?: return

    Card {
        Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
            Text("记忆档案（离线演示模式，仅保存在本机）", fontWeight = FontWeight.Bold)
            ProfileForm(initial = p) { updated ->
                vm.saveProfileLocal(updated)
            }
        }
    }
}

@Composable
private fun ReadonlyProfileSection(vm: MainViewModel) {
    val profile by vm.profile.collectAsState()
    val p = profile ?: return

    Card {
        Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
            Text("记忆档案", fontWeight = FontWeight.Bold)
            listOf(
                "小名" to p.nickname, "出生日期" to p.birthDate,
                "身高体重" to p.heightWeight, "喜欢" to p.likes,
                "害怕" to p.fears, "作息" to p.routine,
                "家人称呼" to p.familyTitles,
            ).forEach { (label, value) ->
                if (value.isNotBlank()) {
                    Text("· $label：$value", style = MaterialTheme.typography.bodyMedium)
                }
            }
            if (p.comfortKit.isNotEmpty()) {
                Text("· 安抚锦囊：", style = MaterialTheme.typography.bodyMedium)
                p.comfortKit.forEach { Text("  - $it", style = MaterialTheme.typography.bodyMedium) }
            }
        }
    }
}

@Composable
private fun ProfileForm(initial: MemoryProfile, onSave: (MemoryProfile) -> Unit) {
    var nickname by rememberSaveable(initial.nickname) { mutableStateOf(initial.nickname) }
    var birthDate by rememberSaveable(initial.birthDate) { mutableStateOf(initial.birthDate) }
    var heightWeight by rememberSaveable(initial.heightWeight) { mutableStateOf(initial.heightWeight) }
    var likes by rememberSaveable(initial.likes) { mutableStateOf(initial.likes) }
    var fears by rememberSaveable(initial.fears) { mutableStateOf(initial.fears) }
    var routine by rememberSaveable(initial.routine) { mutableStateOf(initial.routine) }
    var familyTitles by rememberSaveable(initial.familyTitles) { mutableStateOf(initial.familyTitles) }
    var comfortKit by rememberSaveable(initial.comfortKit.joinToString("\n")) {
        mutableStateOf(initial.comfortKit.joinToString("\n"))
    }

    val fields: List<Pair<String, Pair<String, (String) -> Unit>>> = listOf(
        "小名" to (nickname to { nickname = it }),
        "出生日期（如 2024-03-15）" to (birthDate to { birthDate = it }),
        "身高体重" to (heightWeight to { heightWeight = it }),
        "喜欢（玩具/食物/角色）" to (likes to { likes = it }),
        "害怕（如打雷、吸尘器）" to (fears to { fears = it }),
        "作息（如 21:00 睡觉）" to (routine to { routine = it }),
        "家人称呼（如 爸爸、妈妈、阿婆）" to (familyTitles to { familyTitles = it }),
    )
    fields.forEach { (label, pair) ->
        val (value, setter) = pair
        OutlinedTextField(
            value = value,
            onValueChange = setter,
            label = { Text(label) },
            modifier = Modifier.fillMaxWidth(),
            singleLine = true,
        )
    }
    OutlinedTextField(
        value = comfortKit,
        onValueChange = { comfortKit = it },
        label = { Text("安抚锦囊（每行一条，哭闹时莱德优先使用）") },
        modifier = Modifier.fillMaxWidth(),
        minLines = 2,
    )

    Button(
        onClick = {
            onSave(
                MemoryProfile(
                    nickname = nickname.trim(),
                    birthDate = birthDate.trim(),
                    heightWeight = heightWeight.trim(),
                    likes = likes.trim(),
                    fears = fears.trim(),
                    routine = routine.trim(),
                    familyTitles = familyTitles.trim(),
                    comfortKit = comfortKit.lines()
                        .map { it.trim() }
                        .filter { it.isNotBlank() },
                )
            )
        },
        modifier = Modifier.fillMaxWidth(),
    ) { Text("保存") }
}

// ---------- 莱德人设 ----------

@Composable
private fun PersonaSection(vm: MainViewModel) {
    var loaded by remember { mutableStateOf<BffPersona?>(null) }
    LaunchedEffect(Unit) { vm.loadPersona { loaded = it } }
    val p = loaded ?: return

    Card {
        Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
            Text("莱德人设", fontWeight = FontWeight.Bold)

            var characterName by rememberSaveable(p.characterName) { mutableStateOf(p.characterName) }
            var catchphrase by rememberSaveable(p.catchphrase) { mutableStateOf(p.catchphrase) }
            var speakingStyle by rememberSaveable(p.speakingStyle) { mutableStateOf(p.speakingStyle) }
            var safetyRules by rememberSaveable(p.safetyRules) { mutableStateOf(p.safetyRules) }
            var extraPrompt by rememberSaveable(p.extraPrompt) { mutableStateOf(p.extraPrompt) }

            OutlinedTextField(
                value = characterName, onValueChange = { characterName = it },
                label = { Text("角色名") },
                modifier = Modifier.fillMaxWidth(), singleLine = true,
            )
            OutlinedTextField(
                value = catchphrase, onValueChange = { catchphrase = it },
                label = { Text("口头禅") },
                modifier = Modifier.fillMaxWidth(), singleLine = true,
            )
            OutlinedTextField(
                value = speakingStyle, onValueChange = { speakingStyle = it },
                label = { Text("说话方式（留空用默认）") },
                modifier = Modifier.fillMaxWidth(), minLines = 3,
            )
            OutlinedTextField(
                value = safetyRules, onValueChange = { safetyRules = it },
                label = { Text("安全红线（留空用默认）") },
                modifier = Modifier.fillMaxWidth(), minLines = 3,
            )
            OutlinedTextField(
                value = extraPrompt, onValueChange = { extraPrompt = it },
                label = { Text("补充要求") },
                modifier = Modifier.fillMaxWidth(), minLines = 2,
            )

            Button(
                onClick = {
                    vm.savePersona(
                        BffPersona(
                            characterName = characterName.trim(),
                            catchphrase = catchphrase.trim(),
                            speakingStyle = speakingStyle.trim(),
                            safetyRules = safetyRules.trim(),
                            extraPrompt = extraPrompt.trim(),
                        )
                    ) { }
                },
                modifier = Modifier.fillMaxWidth(),
            ) { Text("保存人设") }
        }
    }
}

// ---------- API Key 保险箱 ----------

@Composable
private fun ProviderKeysSection(vm: MainViewModel) {
    var keys by remember { mutableStateOf<List<BffKeyMasked>>(emptyList()) }
    LaunchedEffect(Unit) { vm.loadKeys { list, _ -> list?.let { keys = it } } }

    Card {
        Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
            Text("API Key 保险箱（只存在服务器上）", fontWeight = FontWeight.Bold)
            Text(
                "换成 DeepSeek / GLM / 豆包都行，改完全家下一次对话立即生效。",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            listOf(
                "llm" to "大脑（LLM）",
                "tts" to "声音（TTS，莱德克隆音色）",
                "asr" to "云端耳朵（ASR 兜底）",
            ).forEach { (provider, label) ->
                ProviderKeyEditor(provider, label, keys) { updated ->
                    vm.saveKey(updated) { vm.loadKeys { list, _ -> list?.let { keys = it } } }
                }
            }
        }
    }
}

@Composable
private fun ProviderKeyEditor(
    provider: String,
    label: String,
    existing: List<BffKeyMasked>,
    onSave: (BffKeyMasked) -> Unit,
) {
    val current = existing.firstOrNull { it.provider == provider }

    Column(Modifier.fillMaxWidth(), verticalArrangement = Arrangement.spacedBy(8.dp)) {
        Text(label, fontWeight = FontWeight.Medium)
        if (current != null && current.api_key_masked.isNotBlank()) {
            Text(
                "已配置：${current.api_key_masked} · ${current.model}",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }

        var baseUrl by remember(provider) { mutableStateOf(current?.base_url ?: "") }
        var model by remember(provider) { mutableStateOf(current?.model ?: "") }
        var apiKey by remember(provider) { mutableStateOf("") }

        OutlinedTextField(
            value = baseUrl, onValueChange = { baseUrl = it },
            label = { Text("接口地址") },
            modifier = Modifier.fillMaxWidth(), singleLine = true,
        )
        OutlinedTextField(
            value = model, onValueChange = { model = it },
            label = { Text("模型 ID") },
            modifier = Modifier.fillMaxWidth(), singleLine = true,
        )
        OutlinedTextField(
            value = apiKey, onValueChange = { apiKey = it },
            label = { Text(if (current == null) "API Key" else "新 API Key（留空不换）") },
            modifier = Modifier.fillMaxWidth(), singleLine = true,
        )

        TextButton(
            onClick = {
                onSave(
                    BffKeyMasked(
                        provider = provider,
                        base_url = baseUrl.trim(),
                        model = model.trim(),
                        // 只在填了新 Key 时上送；留空 = 服务器保留旧 Key
                        api_key_masked = apiKey.trim(),
                    )
                )
                apiKey = ""
            },
            enabled = baseUrl.isNotBlank() && model.isNotBlank(),
        ) { Text("保存") }
    }
}

// ---------- 邀请码与成员 ----------

@Composable
private fun InviteSection(vm: MainViewModel) {
    var inviteCode by remember { mutableStateOf<String?>(null) }
    var members by remember { mutableStateOf<List<com.ryder.buddy.voice.BffMember>>(emptyList()) }
    LaunchedEffect(Unit) { vm.loadMembers { members = it.orEmpty() } }

    Card {
        Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
            Text("家人管理", fontWeight = FontWeight.Bold)
            Text(
                "成员（${members.size}）：${members.joinToString("、") { it.display_name }}",
                style = MaterialTheme.typography.bodyMedium,
            )
            if (inviteCode != null) {
                Text(
                    "新邀请码：$inviteCode（旧的已作废，发给要加入的家人）",
                    color = MaterialTheme.colorScheme.primary,
                    fontWeight = FontWeight.Medium,
                )
            }
            OutlinedButton(onClick = { vm.createInvite { inviteCode = it } }) {
                Text(if (inviteCode == null) "生成邀请码" else "重新生成邀请码")
            }
        }
    }
}
