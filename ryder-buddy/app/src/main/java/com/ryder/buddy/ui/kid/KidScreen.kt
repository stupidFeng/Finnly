package com.ryder.buddy.ui.kid

import android.Manifest
import android.content.pm.PackageManager
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.animation.core.animateFloat
import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.animation.core.infiniteRepeatable
import androidx.compose.animation.core.rememberInfiniteTransition
import androidx.compose.animation.core.tween
import androidx.compose.foundation.background
import androidx.compose.foundation.gestures.detectTapGestures
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Mic
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.alpha
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.scale
import androidx.compose.ui.draw.shadow
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.core.content.ContextCompat
import com.ryder.buddy.MainViewModel
import com.ryder.buddy.TalkState

/**
 * 孩子主界面：一个超大"按住说话"按钮，按状态变色。
 * 界面元素极简——不到三岁的孩子不需要读懂任何文字。
 */
@Composable
fun KidScreen(vm: MainViewModel, onOpenParent: () -> Unit) {
    val talkState by vm.talkState.collectAsState()
    val heard by vm.heard.collectAsState()
    val lastReply by vm.lastReply.collectAsState()
    val context = LocalContext.current

    var hasMicPermission by remember {
        mutableStateOf(
            ContextCompat.checkSelfPermission(
                context, Manifest.permission.RECORD_AUDIO
            ) == PackageManager.PERMISSION_GRANTED
        )
    }
    val permissionLauncher = rememberLauncherForActivityResult(
        ActivityResultContracts.RequestPermission()
    ) { granted -> hasMicPermission = granted }

    LaunchedEffect(Unit) {
        if (!hasMicPermission) permissionLauncher.launch(Manifest.permission.RECORD_AUDIO)
    }

    Box(
        Modifier
            .fillMaxSize()
            .background(Color(0xFFEAF3FF))
    ) {
        // 家长入口：藏在角落的小齿轮，孩子不易误触
        IconButton(
            onClick = onOpenParent,
            modifier = Modifier
                .align(Alignment.TopEnd)
                .padding(12.dp)
        ) {
            Icon(Icons.Filled.Settings, contentDescription = "家长设置", tint = Color(0xFF7A8BA6))
        }

        Column(
            Modifier.align(Alignment.Center),
            horizontalAlignment = Alignment.CenterHorizontally
        ) {
            Text(
                text = "莱德队长",
                fontSize = 34.sp,
                fontWeight = FontWeight.Black,
                color = Color(0xFF16233A)
            )
            Spacer(Modifier.height(4.dp))
            Text(
                text = statusLabel(talkState),
                fontSize = 18.sp,
                color = Color(0xFF48586F)
            )
            Spacer(Modifier.height(36.dp))

            BigTalkButton(
                state = talkState,
                onPressStart = {
                    if (!hasMicPermission) {
                        permissionLauncher.launch(Manifest.permission.RECORD_AUDIO)
                    } else {
                        vm.startListening()
                    }
                },
                onPressEnd = { vm.stopListening() }
            )

            Spacer(Modifier.height(28.dp))
            Text(
                text = when {
                    talkState == TalkState.Listening && heard.isNotBlank() -> "“$heard”"
                    !hasMicPermission -> "需要麦克风权限，才能和莱德说话哦"
                    else -> "按住大按钮，和莱德说话吧！"
                },
                fontSize = 16.sp,
                color = Color(0xFF48586F),
                textAlign = TextAlign.Center,
                modifier = Modifier.padding(horizontal = 32.dp)
            )
        }

        // 莱德最近说的话（也给家长看）
        if (lastReply.isNotBlank() && talkState != TalkState.Listening) {
            Card(
                shape = RoundedCornerShape(20.dp),
                colors = CardDefaults.cardColors(containerColor = Color.White),
                elevation = CardDefaults.cardElevation(defaultElevation = 2.dp),
                modifier = Modifier
                    .align(Alignment.BottomCenter)
                    .padding(20.dp)
                    .fillMaxWidth()
            ) {
                Text(
                    text = lastReply,
                    fontSize = 18.sp,
                    lineHeight = 28.sp,
                    color = Color(0xFF16233A),
                    modifier = Modifier.padding(20.dp)
                )
            }
        }
    }
}

private fun statusLabel(state: TalkState): String = when (state) {
    TalkState.Idle -> "我在等你哦"
    TalkState.Listening -> "莱德正在听…"
    TalkState.Thinking -> "莱德正在想…"
    TalkState.Speaking -> "莱德在说话！"
}

/** 超大圆形按住说话按钮：按下聆听（脉冲呼吸），松开发送；颜色随状态变化 */
@Composable
private fun BigTalkButton(
    state: TalkState,
    onPressStart: () -> Unit,
    onPressEnd: () -> Unit,
) {
    var pressed by remember { mutableStateOf(false) }
    val scale by animateFloatAsState(
        targetValue = if (pressed) 0.93f else 1f,
        label = "pressScale"
    )
    val pulse = rememberInfiniteTransition(label = "pulse")
    val pulseAlpha by pulse.animateFloat(
        initialValue = 1f,
        targetValue = 0.78f,
        animationSpec = infiniteRepeatable(tween(600)),
        label = "pulseAlpha"
    )

    val (bg, label) = when (state) {
        TalkState.Idle -> Color(0xFF2E7CF6) to "按住说话"
        TalkState.Listening -> Color(0xFFEF6C52) to "松开发送"
        TalkState.Thinking -> Color(0xFFF5A623) to "想一想…"
        TalkState.Speaking -> Color(0xFF35B46A) to "打断莱德"
    }
    val alpha = if (state == TalkState.Listening) pulseAlpha else 1f

    Box(
        modifier = Modifier
            .size(230.dp)
            .scale(scale)
            .alpha(alpha)
            .shadow(10.dp, CircleShape)
            .clip(CircleShape)
            .background(bg)
            .pointerInput(Unit) {
                detectTapGestures(
                    onPress = {
                        pressed = true
                        onPressStart()
                        tryAwaitRelease()
                        pressed = false
                        onPressEnd()
                    }
                )
            },
        contentAlignment = Alignment.Center
    ) {
        Column(horizontalAlignment = Alignment.CenterHorizontally) {
            Icon(
                Icons.Filled.Mic,
                contentDescription = null,
                tint = Color.White,
                modifier = Modifier.size(60.dp)
            )
            Text(
                text = label,
                color = Color.White,
                fontSize = 20.sp,
                fontWeight = FontWeight.Bold
            )
        }
    }
}
