package com.ryder.buddy

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.runtime.Composable
import androidx.lifecycle.viewmodel.compose.viewModel
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.rememberNavController
import com.ryder.buddy.ui.kid.KidScreen
import com.ryder.buddy.ui.parent.ParentScreen
import com.ryder.buddy.ui.theme.RyderBuddyTheme

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
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
            ParentScreen(vm = vm, onBack = { navController.popBackStack() })
        }
    }
}
