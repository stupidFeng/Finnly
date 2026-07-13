package com.finn.finnly.data.api

import com.squareup.moshi.Moshi
import com.squareup.moshi.kotlin.reflect.KotlinJsonAdapterFactory
import okhttp3.OkHttpClient
import retrofit2.Retrofit
import retrofit2.converter.moshi.MoshiConverterFactory

/**
 * 网络客户端
 * 使用 jsDelivr CDN 访问 GitHub 仓库的 feed.json
 * jsDelivr 在国内可访问, 自带 CDN 加速, 公开仓库无需 token
 */
object NetworkClient {

    private const val BASE_URL = "https://cdn.jsdelivr.net/gh/stupidFeng/Finnly@main/"

    private val okHttpClient = OkHttpClient.Builder().build()

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
