package com.finn.finnly.data.db

import androidx.room.Dao
import androidx.room.Insert
import androidx.room.OnConflictStrategy
import androidx.room.Query

@Dao
interface FeedDao {
    @Query("SELECT * FROM feed_items ORDER BY totalScore DESC")
    suspend fun getAll(): List<FeedItemEntity>

    @Query("SELECT * FROM feed_items WHERE category = :category ORDER BY totalScore DESC")
    suspend fun getByCategory(category: String): List<FeedItemEntity>

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insertAll(items: List<FeedItemEntity>)

    @Query("DELETE FROM feed_items")
    suspend fun clearAll()

    @Query("SELECT fetchedAt FROM feed_items LIMIT 1")
    suspend fun lastFetchTime(): Long?
}