package com.finn.finnly.data.model

import com.squareup.moshi.JsonClass

@JsonClass(generateAdapter = true)
data class FeedResponse(
    val generatedAt: String = "",
    val fields: Map<String, String> = emptyMap(),
    val feed: List<FeedItem> = emptyList()
)

@JsonClass(generateAdapter = true)
data class FeedItem(
    val id: String = "",
    val title: String = "",
    val category: String = "",
    val hotScore: Double = 0.0,
    val freshness: Double = 0.0,
    val crossSource: Double = 0.0,
    val totalScore: Double = 0.0,
    val sources: List<Source> = emptyList(),
    val summary: String = "",
    val url: String = ""
)

@JsonClass(generateAdapter = true)
data class Source(
    val channel: String = "",
    val rank: Int = 0,
    val hot: Long = 0,
    val url: String = ""
)