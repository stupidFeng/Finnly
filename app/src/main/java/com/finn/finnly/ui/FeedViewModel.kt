package com.finn.finnly.ui

import androidx.lifecycle.LiveData
import androidx.lifecycle.MutableLiveData
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.finn.finnly.data.FeedRepository
import com.finn.finnly.data.model.FeedItem
import kotlinx.coroutines.launch

class FeedViewModel : ViewModel() {

    private lateinit var repository: FeedRepository

    private val _feed = MutableLiveData<List<FeedItem>>()
    val feed: LiveData<List<FeedItem>> = _feed

    private val _loading = MutableLiveData(false)
    val loading: LiveData<Boolean> = _loading

    private val _error = MutableLiveData<String?>()
    val error: LiveData<String?> = _error

    private var currentFilter = "all"

    fun init(repo: FeedRepository) {
        repository = repo
    }

    fun setFilter(filter: String) {
        currentFilter = filter
        viewModelScope.launch {
            emitFiltered(repository.getCached())
        }
    }

    fun refresh() {
        if (!::repository.isInitialized) return
        _loading.value = true
        _error.value = null
        viewModelScope.launch {
            val result = repository.fetchFeed()
            result.onSuccess { items ->
                emitFiltered(items)
            }.onFailure { e ->
                _error.value = e.message ?: "网络失败, 已显示缓存"
                emitFiltered(repository.getCached())
            }
            _loading.value = false
        }
    }

    private suspend fun emitFiltered(items: List<FeedItem>) {
        val filtered = if (currentFilter == "all") items
        else items.filter { it.category == currentFilter }
        _feed.postValue(filtered)
    }
}