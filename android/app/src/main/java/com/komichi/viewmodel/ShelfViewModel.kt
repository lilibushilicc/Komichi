package com.komichi.viewmodel

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.komichi.data.StoreManager
import com.komichi.data.Work
import com.komichi.repository.ComicRepository
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.launch
import javax.inject.Inject

enum class ShelfFilter { ALL, UPDATED, READING }

data class ShelfItem(
    val work: Work,
    val lastChapter: Int,
    val lastReadTime: String,
) {
    val hasUpdate: Boolean get() = work.latestChapterNum > lastChapter
    val isReading: Boolean get() = lastChapter in 1 until work.latestChapterNum
}

data class ShelfUiState(
    val isLoading: Boolean = true,
    val isRefreshing: Boolean = false,
    val error: String? = null,
    val items: List<ShelfItem> = emptyList(),
    val filter: ShelfFilter = ShelfFilter.ALL,
)

@HiltViewModel
class ShelfViewModel @Inject constructor(
    private val repository: ComicRepository,
    private val storeManager: StoreManager,
) : ViewModel() {

    private val _uiState = MutableStateFlow(ShelfUiState())
    val uiState: StateFlow<ShelfUiState> = _uiState.asStateFlow()

    val viewMode: StateFlow<Int> = storeManager.shelfViewMode
        .stateIn(viewModelScope, SharingStarted.Eagerly, 0)

    init {
        loadShelf()
    }

    fun loadShelf() {
        _uiState.value = _uiState.value.copy(isLoading = true, error = null)
        viewModelScope.launch {
            runCatching {
                val bookmarks = repository.getBookmarks()
                val works = runCatching { repository.getWorkList() }.getOrDefault(emptyList())
                val workMap = works.associateBy { it.id }
                bookmarks.mapNotNull { bm ->
                    val work = bm.work ?: workMap[bm.workId] ?: return@mapNotNull null
                    ShelfItem(work, bm.chapterNum, bm.lastReadTime)
                }.sortedByDescending { it.lastReadTime }
            }.onSuccess { items ->
                _uiState.value = _uiState.value.copy(
                    isLoading = false,
                    isRefreshing = false,
                    error = null,
                    items = items,
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
        loadShelf()
    }

    fun setFilter(filter: ShelfFilter) {
        _uiState.value = _uiState.value.copy(filter = filter)
    }

    fun toggleViewMode() {
        viewModelScope.launch {
            storeManager.saveShelfViewMode(if (viewMode.value == 0) 1 else 0)
        }
    }

    fun filteredItems(): List<ShelfItem> = when (_uiState.value.filter) {
        ShelfFilter.ALL -> _uiState.value.items
        ShelfFilter.UPDATED -> _uiState.value.items.filter { it.hasUpdate }
        ShelfFilter.READING -> _uiState.value.items.filter { it.isReading }
    }
}
