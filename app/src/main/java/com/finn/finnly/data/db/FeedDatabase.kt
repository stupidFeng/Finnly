package com.finn.finnly.data.db

import android.content.Context
import androidx.room.Database
import androidx.room.Room
import androidx.room.RoomDatabase

@Database(entities = [FeedItemEntity::class], version = 1, exportSchema = false)
abstract class FeedDatabase : RoomDatabase() {
    abstract fun feedDao(): FeedDao

    companion object {
        @Volatile private var INSTANCE: FeedDatabase? = null

        fun get(context: Context): FeedDatabase =
            INSTANCE ?: synchronized(this) {
                INSTANCE ?: Room.databaseBuilder(
                    context.applicationContext,
                    FeedDatabase::class.java,
                    "finnly.db"
                ).build().also { INSTANCE = it }
            }
    }
}