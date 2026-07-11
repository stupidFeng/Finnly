package com.finn.finnly.data.db

import androidx.room.Entity
import androidx.room.PrimaryKey

@Entity(tableName = "feed_items")
data class FeedItemEntity(
    @PrimaryKey val id: String,
    val title: String,
    val category: String,
    val hotScore: Double,
    val freshness: Double,
    val crossSource: Double,
    val totalScore: Double,
    val sourceCount: Int,
    val summary: String,
    val url: String,
    val generatedAt: String,
    val fetchedAt: Long = System.currentTimeMillis()
)