package com.komichi.viewmodel

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.komichi.api.ImportResponse
import com.komichi.api.SourceSearchItem
import com.komichi.data.StoreManager
import com.komichi.data.Work
import com.komichi.repository.ComicRepository
import com.komichi.util.isToday
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.launch
import javax.inject.Inject

data class ContinueItem(val work: Work, val lastChapter: Int)

enum class SearchMode { LOCAL, SOURCE }

data class HomeUiState(
    val isLoading: Boolean = true,
    val isRefreshing: Boolean = false,
    val error: String? = null,
    val todayUpdates: List<Work> = emptyList(),
    val continueReading: List<ContinueItem> = emptyList(),
    val hotWorks: List<Work> = emptyList(),
    val allWorks: List<Work> = emptyList(),
    // 本地搜索
    val searchQuery: String = "",
    val searchResults: List<Work> = emptyList(),
    // 源站搜索
    val searchMode: SearchMode = SearchMode.LOCAL,
    val isSearching: Boolean = false,
    val sourceSearchResults: Map<String, List<SourceSearchItem>> = emptyMap(),
    val searchError: String? = null,
    // 导入
    val importingUrl: String? = null,
    val importMessage: String? = null,
)

@HiltViewModel
class HomeViewModel @Inject constructor(
    private val repository: ComicRepository,
    private val storeManager: StoreManager,
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

    // ---------- 本地搜索 ----------

    fun setSearchQuery(query: String) {
        val results = if (query.isBlank()) emptyList() else filterWorks(_uiState.value.allWorks, query)
        _uiState.value = _uiState.value.copy(
            searchQuery = query,
            searchResults = results,
            importMessage = null,
        )
    }

    // ---------- 搜索模式切换 ----------

    fun setSearchMode(mode: SearchMode) {
        _uiState.value = _uiState.value.copy(
            searchMode = mode,
            searchQuery = "",
            searchResults = emptyList(),
            sourceSearchResults = emptyMap(),
            searchError = null,
            importMessage = null,
        )
    }

    // ---------- 源站搜索 ----------

    fun searchSourceWorks(keyword: String) {
        val q = keyword.trim()
        if (q.isBlank()) return
        _uiState.value = _uiState.value.copy(
            isSearching = true,
            searchError = null,
            sourceSearchResults = emptyMap(),
            importMessage = null,
        )
        viewModelScope.launch {
            runCatching { repository.searchSourceWorks(q) }
                .onSuccess { resp ->
                    // 按启用的源过滤搜索结果
                    val disabled = storeManager.disabledSources.first()
                    val filtered = resp.results.filterKeys { it !in disabled }
                    _uiState.value = _uiState.value.copy(
                        isSearching = false,
                        sourceSearchResults = filtered,
                        searchError = if (filtered.isEmpty()) "没有找到结果" else null,
                    )
                }
                .onFailure { e ->
                    _uiState.value = _uiState.value.copy(
                        isSearching = false,
                        searchError = e.message ?: "搜索失败，请检查 VPS 服务是否运行",
                    )
                }
        }
    }

    // ---------- 从源站导入 ----------

    fun importFromSource(sourceUrl: String) {
        _uiState.value = _uiState.value.copy(
            importingUrl = sourceUrl,
            importMessage = null,
        )
        viewModelScope.launch {
            runCatching { repository.importFromSource(sourceUrl) }
                .onSuccess { resp: ImportResponse ->
                    _uiState.value = _uiState.value.copy(
                        importingUrl = null,
                        importMessage = "导入成功: ${resp.title} (${resp.chapterCount} 话)",
                    )
                    // 导入成功后刷新首页列表
                    loadHome()
                }
                .onFailure { e ->
                    _uiState.value = _uiState.value.copy(
                        importingUrl = null,
                        importMessage = "导入失败: ${e.message ?: "未知错误"}",
                    )
                }
        }
    }

    fun clearImportMessage() {
        _uiState.value = _uiState.value.copy(importMessage = null)
    }

    fun clearSearchError() {
        _uiState.value = _uiState.value.copy(searchError = null)
    }

    // ---------- 内部方法 ----------

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
