package com.ryder.buddy

import android.graphics.Color
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.SystemBarStyle
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.runtime.Composable
import androidx.lifecycle.viewmodel.compose.viewModel
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.rememberNavController
import com.ryder.buddy.ui.kid.KidScreen
import com.ryder.buddy.ui.parent.FamilyHistoryScreen
import com.ryder.buddy.ui.parent.ParentScreen
import com.ryder.buddy.ui.theme.RyderBuddyTheme

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        // 全屏沉浸：画面延伸到状态栏/导航栏底下，图标用深色（App 是浅色背景）
        enableEdgeToEdge(
            statusBarStyle = SystemBarStyle.light(
                Color.TRANSPARENT, Color.TRANSPARENT
            ),
            navigationBarStyle = SystemBarStyle.light(
                Color.TRANSPARENT, Color.TRANSPARENT
            ),
        )
        super.onCreate(savedInstanceState)
        setContent {
            RyderBuddyTheme {
                RyderBuddyApp()
            }
        }
    }
}

@Composable
fun RyderBuddyApp() {
    // Activity 级共享：两个页面复用同一个 ASR / TTS 实例和对话状态
    val vm: MainViewModel = viewModel()
    val navController = rememberNavController()

    NavHost(navController = navController, startDestination = "kid") {
        composable("kid") {
            KidScreen(vm = vm, onOpenParent = { navController.navigate("parent") })
        }
        composable("parent") {
            ParentScreen(
                vm = vm,
                onOpenHistory = { navController.navigate("history") },
                onBack = { navController.popBackStack() },
            )
        }
        composable("history") {
            FamilyHistoryScreen(vm = vm, onBack = { navController.popBackStack() })
        }
    }
}
