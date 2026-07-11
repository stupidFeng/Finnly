package com.finn.finnly.data

import com.finn.finnly.data.api.NetworkClient
import com.finn.finnly.data.db.FeedDao
import com.finn.finnly.data.db.FeedItemEntity
import com.finn.finnly.data.model.FeedItem

class FeedRepository(private val dao: FeedDao) {

    suspend fun fetchFeed(): Result<List<FeedItem>> {
        return try {
            val resp = NetworkClient.feedApi.getFeed()
            val entities = resp.feed.map { it.toEntity(resp.generatedAt) }
            dao.clearAll()
            dao.insertAll(entities)
            Result.success(resp.feed)
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    suspend fun getCached(): List<FeedItem> {
        return dao.getAll().map { it.toModel() }
    }

    suspend fun getCachedByCategory(category: String): List<FeedItem> {
        return dao.getByCategory(category).map { it.toModel() }
    }

    suspend fun lastFetchTime(): Long? = dao.lastFetchTime()

    private fun FeedItem.toEntity(generatedAt: String) = FeedItemEntity(
        id = id,
        title = title,
        category = category,
        hotScore = hotScore,
        freshness = freshness,
        crossSource = crossSource,
        totalScore = totalScore,
        sourceCount = sources.size,
        summary = summary,
        url = url,
        generatedAt = generatedAt
    )

    private fun FeedItemEntity.toModel() = FeedItem(
        id = id,
        title = title,
        category = category,
        hotScore = hotScore,
        freshness = freshness,
        crossSource = crossSource,
        totalScore = totalScore,
        sources = emptyList(),
        summary = summary,
        url = url
    )
}