import java.util.Properties
import java.io.FileReader

plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
    id("com.google.devtools.ksp")
}

// Read GitHub token from local.properties (not checked into git)
val localProperties = Properties()
val localPropertiesFile = rootProject.file("local.properties")
if (localPropertiesFile.exists()) {
    FileReader(localPropertiesFile).use { reader -> localProperties.load(reader) }
}
val githubToken: String = localProperties.getProperty("finnly.github.token") ?: ""

android {
    namespace = "com.finn.finnly"
    compileSdk = 34

    defaultConfig {
        applicationId = "com.finn.finnly"
        minSdk = 24
        targetSdk = 34
        versionCode = 1
        versionName = "1.0"

        // Inject GitHub token for accessing private repo raw URL
        buildConfigField("String", "GITHUB_TOKEN", "\"$githubToken\"")
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    kotlinOptions {
        jvmTarget = "17"
    }

    buildFeatures {
        buildConfig = true
        viewBinding = true
    }

    // 固定签名: 避免每次 CI 构建签名不同导致必须卸载旧 APK
    // 使用项目内 finnly.keystore (debug/release 共用), 仓库公开但 keystore 仅用于调试构建
    signingConfigs {
        create("shared") {
            storeFile = file("finnly.keystore")
            storePassword = "finnly123"
            keyAlias = "finnly"
            keyPassword = "finnly123"
        }
    }

    buildTypes {
        debug {
            signingConfig = signingConfigs.getByName("shared")
        }
        release {
            isMinifyEnabled = false
            signingConfig = signingConfigs.getByName("shared")
            proguardFiles(
                getDefaultProguardFile("proguard-android-optimize.txt"),
                "proguard-rules.pro"
            )
        }
    }
}

dependencies {
    implementation("androidx.core:core-ktx:1.12.0")
    implementation("androidx.appcompat:appcompat:1.6.1")
    implementation("com.google.android.material:material:1.11.0")
    implementation("androidx.constraintlayout:constraintlayout:2.1.4")

    // Lifecycle / ViewModel / LiveData
    implementation("androidx.lifecycle:lifecycle-viewmodel-ktx:2.7.0")
    implementation("androidx.lifecycle:lifecycle-livedata-ktx:2.7.0")
    implementation("androidx.lifecycle:lifecycle-runtime-ktx:2.7.0")

    // Coroutines
    implementation("org.jetbrains.kotlinx:kotlinx-coroutines-android:1.7.3")

    // Retrofit + OkHttp + Moshi (JSON 解析)
    implementation("com.squareup.retrofit2:retrofit:2.9.0")
    implementation("com.squareup.retrofit2:converter-moshi:2.9.0")
    implementation("com.squareup.moshi:moshi-kotlin:1.15.0")
    implementation("com.squareup.okhttp3:okhttp:4.12.0")

    // Room (本地缓存) - ksp 注解处理器生成 _Impl 类
    implementation("androidx.room:room-runtime:2.6.1")
    implementation("androidx.room:room-ktx:2.6.1")
    ksp("androidx.room:room-compiler:2.6.1")

    // SwipeRefreshLayout (下拉刷新)
    implementation("androidx.swiperefreshlayout:swiperefreshlayout:1.1.0")
}
