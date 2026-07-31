package com.komichi.viewmodel

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.komichi.data.Work
import com.komichi.repository.ComicRepository
import com.komichi.util.isToday
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import javax.inject.Inject

data class ContinueItem(val work: Work, val lastChapter: Int)

data class HomeUiState(
    val isLoading: Boolean = true,
    val isRefreshing: Boolean = false,
    val error: String? = null,
    val todayUpdates: List<Work> = emptyList(),
    val continueReading: List<ContinueItem> = emptyList(),
    val hotWorks: List<Work> = emptyList(),
    val allWorks: List<Work> = emptyList(),
    val searchQuery: String = "",
    val searchResults: List<Work> = emptyList(),
)

@HiltViewModel
class HomeViewModel @Inject constructor(
    private val repository: ComicRepository,
) : ViewModel() {

    private val _uiState = MutableStateFlow(HomeUiState())
    val uiState: StateFlow<HomeUiState> = _uiState.asStateFlow()

    init {
        loadHome()
    }

    fun loadHome() {
        _uiState.value = _uiState.value.copy(isLoading = true, error = null)
        viewModelScope.launch {
            val result = runCatching {
                val works = repository.getWorkList()
                val bookmarks = runCatching { repository.getBookmarks() }.getOrDefault(emptyList())
                HomeData(works, bookmarks)
            }
            result.onSuccess { (works, bookmarks) ->
                val today = works.filter { isToday(it.updateTime) || isToday(it.createTime) }
                val workMap = works.associateBy { it.id }
                val continueItems = bookmarks
                    .filter { it.chapterNum > 0 }
                    .sortedByDescending { it.lastReadTime }
                    .take(10)
                    .mapNotNull { bm ->
                        val w = bm.work ?: workMap[bm.workId]
                        w?.let { ContinueItem(it, bm.chapterNum) }
                    }
                val hot = works.sortedByDescending { it.latestChapterNum }.take(10)
                _uiState.value = _uiState.value.copy(
                    isLoading = false,
                    isRefreshing = false,
                    error = null,
                    todayUpdates = today,
                    continueReading = continueItems,
                    hotWorks = hot,
                    allWorks = works,
                    searchResults = if (_uiState.value.searchQuery.isNotBlank()) {
                        filterWorks(works, _uiState.value.searchQuery)
                    } else {
                        emptyList()
                    },
                )
            }.onFailure { e ->
                _uiState.value = _uiState.value.copy(
                    isLoading = false,
                    isRefreshing = false,
                    error = e.message ?: "加载失败",
                )
            }
        }
    }

    fun refresh() {
        _uiState.value = _uiState.value.copy(isRefreshing = true)
        loadHome()
    }

    fun setSearchQuery(query: String) {
        val results = if (query.isBlank()) emptyList() else filterWorks(_uiState.value.allWorks, query)
        _uiState.value = _uiState.value.copy(searchQuery = query, searchResults = results)
    }

    private fun filterWorks(works: List<Work>, query: String): List<Work> {
        val q = query.trim().lowercase()
        return works.filter {
            it.title.lowercase().contains(q) ||
                it.category.lowercase().contains(q) ||
                it.summary.lowercase().contains(q)
        }
    }

    private data class HomeData(val works: List<Work>, val bookmarks: List<com.komichi.data.Bookmark>)
}
