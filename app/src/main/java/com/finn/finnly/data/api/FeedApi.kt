package com.finn.finnly.data.api

import com.finn.finnly.data.model.FeedResponse
import retrofit2.http.GET

interface FeedApi {
    @GET("docs/feed.json")
    suspend fun getFeed(): FeedResponse
}