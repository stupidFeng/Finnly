package com.ryder.buddy.ui.kid

import android.Manifest
import android.content.pm.PackageManager
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.animation.core.animateFloat
import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.animation.core.infiniteRepeatable
import androidx.compose.animation.core.RepeatMode
import androidx.compose.animation.core.rememberInfiniteTransition
import androidx.compose.animation.core.tween
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.gestures.detectTapGestures
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.offset
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.statusBarsPadding
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
import androidx.compose.ui.draw.rotate
import androidx.compose.ui.draw.scale
import androidx.compose.ui.draw.shadow
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.core.content.ContextCompat
import com.ryder.buddy.MainViewModel
import com.ryder.buddy.R
import com.ryder.buddy.TalkState

/**
 * 孩子主界面：莱德头像 + 超大"按住说话"按钮 + 气泡式对话。
 * 界面文字极简——不到三岁的孩子主要通过颜色和图标理解状态。
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
            .background(
                Brush.verticalGradient(
                    colors = listOf(
                        Color(0xFF9FD6FF), // 天空蓝
                        Color(0xFFD9EEFF), // 云隙浅蓝
                        Color(0xFFE3F4E6), // 草地浅绿
                    )
                )
            )
    ) {
        // ---------- 背景装饰：云朵 + 六犬代表色狗爪 + 骨头 ----------
        CloudDecoration(modifier = Modifier.align(Alignment.TopStart).offset(x = (-14).dp, y = 26.dp), size = 96.dp)
        CloudDecoration(modifier = Modifier.align(Alignment.TopEnd).offset(x = (-6).dp, y = 104.dp), size = 64.dp)

        // 各队员代表色的爪印
        PawDecoration(Rotation = -18f, color = Color(0xFF2E5FA3), modifier = Modifier.align(Alignment.TopStart).offset(x = 26.dp, y = 240.dp))   // 阿奇·警蓝
        PawDecoration(Rotation = 14f, color = Color(0xFFE63946), modifier = Modifier.align(Alignment.TopEnd).offset(x = (-30).dp, y = 220.dp))   // 毛毛·红
        PawDecoration(Rotation = 32f, color = Color(0xFFFFFFFF), modifier = Modifier.align(Alignment.TopStart).offset(x = 4.dp, y = 150.dp))     // 白爪
        PawDecoration(Rotation = -8f, color = Color(0xFF43A047), modifier = Modifier.align(Alignment.TopEnd).offset(x = (-8).dp, y = 350.dp))    // 灰灰·绿
        PawDecoration(Rotation = 12f, color = Color(0xFFF06292), modifier = Modifier.align(Alignment.TopStart).offset(x = 40.dp, y = 400.dp))    // 天天·粉
        PawDecoration(Rotation = 18f, color = Color(0xFFF57C00), modifier = Modifier.align(Alignment.BottomStart).offset(x = 40.dp, y = (-200).dp))  // 路马·橙
        PawDecoration(Rotation = -14f, color = Color(0xFFF9A825), modifier = Modifier.align(Alignment.BottomEnd).offset(x = (-36).dp, y = (-210).dp)) // 小砾·黄
        PawDecoration(Rotation = 25f, color = Color(0xFFFFFFFF), modifier = Modifier.align(Alignment.BottomEnd).offset(x = (-10).dp, y = (-150).dp))  // 白爪

        // 散落的骨头
        BoneDecoration(Rotation = -15f, modifier = Modifier.align(Alignment.TopStart).offset(x = 62.dp, y = 190.dp))
        BoneDecoration(Rotation = 20f, modifier = Modifier.align(Alignment.TopEnd).offset(x = (-70).dp, y = 320.dp))
        BoneDecoration(Rotation = -10f, modifier = Modifier.align(Alignment.BottomStart).offset(x = 16.dp, y = (-230).dp))

        // ---------- 家长入口：藏在角落的小齿轮（避开状态栏） ----------
        IconButton(
            onClick = onOpenParent,
            modifier = Modifier
                .align(Alignment.TopEnd)
                .statusBarsPadding()
                .padding(8.dp)
        ) {
            Icon(Icons.Filled.Settings, contentDescription = "家长设置", tint = Color(0xFF7A8BA6))
        }

        // ---------- 主体内容 ----------
        Column(
            Modifier.align(Alignment.Center),
            horizontalAlignment = Alignment.CenterHorizontally
        ) {
            // 莱德头像（圆形裁剪 + 白色描边）
            Box(
                modifier = Modifier
                    .size(96.dp)
                    .shadow(8.dp, CircleShape)
                    .clip(CircleShape)
                    .border(4.dp, Color.White, CircleShape)
            ) {
                Image(
                    painter = painterResource(R.drawable.ic_ryder_avatar),
                    contentDescription = "莱德队长",
                    modifier = Modifier.fillMaxSize(),
                    contentScale = ContentScale.Crop
                )
            }

            Spacer(Modifier.height(6.dp))

            // 状态文字（大字、少字，孩子靠颜色区分）
            Text(
                text = statusLabel(talkState),
                fontSize = 26.sp,
                fontWeight = FontWeight.Black,
                color = statusColor(talkState)
            )

            Spacer(Modifier.height(18.dp))

            // 超大按钮 + 毛毛头像装饰
            Box(contentAlignment = Alignment.Center) {
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
                // 毛毛头像在按钮右下角探出
                Box(
                    modifier = Modifier
                        .align(Alignment.BottomEnd)
                        .offset(x = 6.dp, y = 6.dp)
                        .size(52.dp)
                        .shadow(6.dp, CircleShape)
                        .clip(CircleShape)
                        .border(3.dp, Color.White, CircleShape)
                ) {
                    Image(
                        painter = painterResource(R.drawable.ic_marshall_avatar),
                        contentDescription = "毛毛",
                        modifier = Modifier.fillMaxSize(),
                        contentScale = ContentScale.Crop
                    )
                }
            }

            Spacer(Modifier.height(14.dp))

            // 听到的内容 / 提示文字
            Text(
                text = when {
                    talkState == TalkState.Listening && heard.isNotBlank() -> "「$heard」"
                    !hasMicPermission -> "点这里，允许录音哦"
                    else -> "按住大按钮，和莱德说话！"
                },
                fontSize = 17.sp,
                color = Color(0xFF48586F),
                textAlign = TextAlign.Center,
                modifier = Modifier.padding(horizontal = 32.dp)
            )

            Spacer(Modifier.height(14.dp))

            // ---------- 汪汪队全员集合 ----------
            PawPatrolTeamRow(talkState = talkState)
        }

        // ---------- 底部：莱德说的话（气泡式卡片，避开导航栏） ----------
        if (lastReply.isNotBlank() && talkState != TalkState.Listening) {
            Card(
                shape = RoundedCornerShape(24.dp),
                colors = CardDefaults.cardColors(containerColor = Color.White),
                elevation = CardDefaults.cardElevation(defaultElevation = 3.dp),
                modifier = Modifier
                    .align(Alignment.BottomCenter)
                    .navigationBarsPadding()
                    .padding(16.dp)
                    .fillMaxWidth()
            ) {
                Row(
                    modifier = Modifier.padding(16.dp),
                    verticalAlignment = Alignment.Top
                ) {
                    // 小莱德头像
                    Box(
                        modifier = Modifier
                            .size(40.dp)
                            .clip(CircleShape)
                            .border(2.dp, Color(0xFFEAF3FF), CircleShape)
                    ) {
                        Image(
                            painter = painterResource(R.drawable.ic_ryder_avatar),
                            contentDescription = null,
                            modifier = Modifier.fillMaxSize(),
                            contentScale = ContentScale.Crop
                        )
                    }
                    Spacer(Modifier.size(12.dp))
                    Text(
                        text = lastReply,
                        fontSize = 18.sp,
                        lineHeight = 28.sp,
                        color = Color(0xFF16233A),
                        modifier = Modifier.weight(1f)
                    )
                }
            }
        }
    }
}

/** 状态文字（极简，孩子靠颜色和图标理解） */
private fun statusLabel(state: TalkState): String = when (state) {
    TalkState.Idle -> "和莱德说话"
    TalkState.Listening -> "莱德在听…"
    TalkState.Thinking -> "莱德在想…"
    TalkState.Speaking -> "莱德在说话！"
}

/** 状态颜色 */
private fun statusColor(state: TalkState): Color = when (state) {
    TalkState.Idle -> Color(0xFF16233A)
    TalkState.Listening -> Color(0xFFEF6C52)
    TalkState.Thinking -> Color(0xFFF5A623)
    TalkState.Speaking -> Color(0xFF35B46A)
}

/** 背景狗爪装饰（可指定队员代表色） */
@Composable
private fun PawDecoration(
    Rotation: Float,
    color: Color,
    modifier: Modifier = Modifier,
) {
    Icon(
        painter = painterResource(R.drawable.ic_paw),
        contentDescription = null,
        tint = color,
        modifier = modifier
            .size(64.dp)
            .alpha(0.16f)
            .rotate(Rotation)
    )
}

/** 背景骨头装饰 */
@Composable
private fun BoneDecoration(
    Rotation: Float,
    modifier: Modifier = Modifier,
) {
    Icon(
        painter = painterResource(R.drawable.ic_bone),
        contentDescription = null,
        tint = Color(0xFFFFFDF5),
        modifier = modifier
            .size(46.dp)
            .alpha(0.55f)
            .rotate(Rotation)
    )
}

/** 背景云朵装饰 */
@Composable
private fun CloudDecoration(
    modifier: Modifier = Modifier,
    size: Dp = 96.dp,
) {
    Icon(
        painter = painterResource(R.drawable.ic_cloud),
        contentDescription = null,
        tint = Color.White,
        modifier = modifier
            .size(size)
            .alpha(0.85f)
    )
}

/** 汪汪队全员集合栏：六只狗狗小头像；莱德说话时集体"欢呼"跳动 */
@Composable
private fun PawPatrolTeamRow(talkState: TalkState) {
    val cheering = talkState == TalkState.Speaking
    Row(
        horizontalArrangement = Arrangement.spacedBy(10.dp),
        verticalAlignment = Alignment.Bottom,
    ) {
        TeamDogAvatar(R.drawable.ic_chase_avatar, "阿奇", cheering, index = 0)
        TeamDogAvatar(R.drawable.ic_marshall_avatar, "毛毛", cheering, index = 1)
        TeamDogAvatar(R.drawable.ic_skye_avatar, "天天", cheering, index = 2)
        TeamDogAvatar(R.drawable.ic_rocky_avatar, "灰灰", cheering, index = 3)
        TeamDogAvatar(R.drawable.ic_zuma_avatar, "路马", cheering, index = 4)
        TeamDogAvatar(R.drawable.ic_rubble_avatar, "小砾", cheering, index = 5)
    }
}

/** 单只狗狗头像：cheering 时错峰上下跳动，像啦啦队 */
@Composable
private fun TeamDogAvatar(
    resId: Int,
    name: String,
    cheering: Boolean,
    index: Int,
) {
    val transition = rememberInfiniteTransition(label = name)
    val bounce by transition.animateFloat(
        initialValue = 0f,
        targetValue = 1f,
        animationSpec = infiniteRepeatable(
            animation = tween(450, delayMillis = index * 80),
            repeatMode = RepeatMode.Reverse
        ),
        label = "bounce$name"
    )
    val offsetY = if (cheering) (-7f * bounce).dp else 0.dp

    Box(
        modifier = Modifier
            .offset(y = offsetY)
            .size(40.dp)
            .shadow(3.dp, CircleShape)
            .clip(CircleShape)
            .border(2.dp, Color.White, CircleShape)
    ) {
        Image(
            painter = painterResource(resId),
            contentDescription = name,
            modifier = Modifier.fillMaxSize(),
            contentScale = ContentScale.Crop
        )
    }
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
            .size(220.dp)
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
                modifier = Modifier.size(56.dp)
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
