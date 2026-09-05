package com.ryder.buddy.ui.parent

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material3.Button
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import com.ryder.buddy.MainViewModel
import com.ryder.buddy.data.LlmSettings
import com.ryder.buddy.data.MemoryProfile

/**
 * 家长面板：注入记忆档案 + 配置莱德的大脑。
 * 所有字段留空也完全可用（莱德只保留人设与安全红线）。
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ParentScreen(vm: MainViewModel, onBack: () -> Unit) {
    val profile by vm.profile.collectAsState()
    val llm by vm.llmSettings.collectAsState()
    val ttsReady by vm.ttsReady.collectAsState()

    // 表单只在数据首次加载时初始化，之后由家长自由编辑，保存后才回写
    var form by remember { mutableStateOf(MemoryProfile()) }
    var llmForm by remember { mutableStateOf(LlmSettings()) }
    LaunchedEffect(profile) { profile?.let { form = it } }
    LaunchedEffect(llm) { llm?.let { llmForm = it } }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("家长面板") },
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = "返回")
                    }
                }
            )
        }
    ) { padding ->
        Column(
            modifier = Modifier
                .padding(padding)
                .fillMaxSize()
                .verticalScroll(rememberScrollState())
                .padding(horizontal = 16.dp, vertical = 8.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp)
        ) {
            SectionTitle("关于她（莱德的记忆）")
            OutlinedTextField(
                value = form.nickname,
                onValueChange = { form = form.copy(nickname = it) },
                label = { Text("小名") },
                modifier = Modifier.fillMaxWidth()
            )
            OutlinedTextField(
                value = form.birthDate,
                onValueChange = { form = form.copy(birthDate = it) },
                label = { Text("出生日期（如 2024-03-15，年龄自动计算）") },
                modifier = Modifier.fillMaxWidth()
            )
            OutlinedTextField(
                value = form.heightWeight,
                onValueChange = { form = form.copy(heightWeight = it) },
                label = { Text("身高体重（如 92cm / 13.5kg）") },
                modifier = Modifier.fillMaxWidth()
            )
            OutlinedTextField(
                value = form.likes,
                onValueChange = { form = form.copy(likes = it) },
                label = { Text("喜欢什么（玩具 / 食物 / 角色）") },
                modifier = Modifier.fillMaxWidth(),
                minLines = 2
            )
            OutlinedTextField(
                value = form.fears,
                onValueChange = { form = form.copy(fears = it) },
                label = { Text("害怕什么（如打雷、吸尘器）") },
                modifier = Modifier.fillMaxWidth()
            )
            OutlinedTextField(
                value = form.routine,
                onValueChange = { form = form.copy(routine = it) },
                label = { Text("作息（如 21:00 睡觉，午睡 13:00-15:00）") },
                modifier = Modifier.fillMaxWidth()
            )
            OutlinedTextField(
                value = form.familyTitles,
                onValueChange = { form = form.copy(familyTitles = it) },
                label = { Text("家人称呼（如 爸爸、妈妈、奶奶）") },
                modifier = Modifier.fillMaxWidth()
            )
            OutlinedTextField(
                value = form.comfortKit.joinToString("\n"),
                onValueChange = { text ->
                    form = form.copy(
                        comfortKit = text.lines().map { it.trim() }.filter { it.isNotEmpty() }
                    )
                },
                label = { Text("安抚锦囊（每行一条，哭闹时莱德优先使用）") },
                modifier = Modifier.fillMaxWidth(),
                minLines = 3
            )

            SectionTitle("莱德的大脑（大模型）")
            Row(verticalAlignment = Alignment.CenterVertically) {
                Column(Modifier.weight(1f)) {
                    Text("离线演示模式", style = MaterialTheme.typography.bodyLarge)
                    Text(
                        "开启后无需 API Key，使用内置应答",
                        style = MaterialTheme.typography.bodySmall
                    )
                }
                Switch(
                    checked = llmForm.useStub,
                    onCheckedChange = { llmForm = llmForm.copy(useStub = it) }
                )
            }
            OutlinedTextField(
                value = llmForm.baseUrl,
                onValueChange = { llmForm = llmForm.copy(baseUrl = it) },
                label = { Text("接口地址（OpenAI 兼容）") },
                modifier = Modifier.fillMaxWidth()
            )
            OutlinedTextField(
                value = llmForm.model,
                onValueChange = { llmForm = llmForm.copy(model = it) },
                label = { Text("模型 ID（豆包 / GLM / 通义均可）") },
                modifier = Modifier.fillMaxWidth()
            )
            OutlinedTextField(
                value = llmForm.apiKey,
                onValueChange = { llmForm = llmForm.copy(apiKey = it) },
                label = { Text("API Key") },
                modifier = Modifier.fillMaxWidth()
            )

            OutlinedButton(onClick = { vm.testVoice() }, modifier = Modifier.fillMaxWidth()) {
                Text("试听莱德的声音")
            }

            Text(
                text = "语音识别：${
                    if (vm.asrAvailable) "系统语音识别可用（建议后续接入讯飞儿童引擎）"
                    else "当前设备不可用，需接入云端 ASR"
                }\n语音合成：${
                    if (ttsReady) "系统中文 TTS 可用（后续可换火山引擎声音复刻，克隆莱德音色）"
                    else "中文 TTS 未就绪"
                }",
                style = MaterialTheme.typography.bodySmall
            )

            Button(
                onClick = {
                    vm.saveProfile(form)
                    vm.saveLlmSettings(llmForm)
                    onBack()
                },
                modifier = Modifier.fillMaxWidth()
            ) { Text("保存") }

            Spacer(Modifier.height(24.dp))
        }
    }
}

@Composable
private fun SectionTitle(text: String) {
    Text(
        text = text,
        style = MaterialTheme.typography.titleMedium,
        color = MaterialTheme.colorScheme.primary,
        modifier = Modifier.padding(top = 12.dp)
    )
}
