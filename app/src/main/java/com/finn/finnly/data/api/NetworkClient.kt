package com.finn.finnly.data.api

import com.finn.finnly.BuildConfig
import com.squareup.moshi.Moshi
import com.squareup.moshi.kotlin.reflect.KotlinJsonAdapterFactory
import okhttp3.Interceptor
import okhttp3.OkHttpClient
import retrofit2.Retrofit
import retrofit2.converter.moshi.MoshiConverterFactory

/**
 * 网络客户端
 * BASE_URL 指向 raw.githubusercontent.com (私有仓库需 Authorization header)
 */
object NetworkClient {

    private const val BASE_URL = "https://raw.githubusercontent.com/stupidFeng/Finnly/main/"

    // OkHttp interceptor: add GitHub token for private repo access
    private val authInterceptor = Interceptor { chain ->
        val token = BuildConfig.GITHUB_TOKEN
        if (token.isEmpty()) {
            chain.proceed(chain.request())
        } else {
            val newRequest = chain.request().newBuilder()
                .header("Authorization", "token $token")
                .build()
            chain.proceed(newRequest)
        }
    }

    private val okHttpClient = OkHttpClient.Builder()
        .addInterceptor(authInterceptor)
        .build()

    private val moshi = Moshi.Builder()
        .add(KotlinJsonAdapterFactory())
        .build()

    val feedApi: FeedApi by lazy {
        Retrofit.Builder()
            .baseUrl(BASE_URL)
            .client(okHttpClient)
            .addConverterFactory(MoshiConverterFactory.create(moshi))
            .build()
            .create(FeedApi::class.java)
    }
}