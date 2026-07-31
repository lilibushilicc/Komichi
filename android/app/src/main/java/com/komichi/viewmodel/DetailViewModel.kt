package com.komichi.viewmodel

import androidx.lifecycle.SavedStateHandle
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.komichi.data.Chapter
import com.komichi.data.Work
import com.komichi.repository.ComicRepository
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import javax.inject.Inject

data class DetailUiState(
    val isLoading: Boolean = true,
    val error: String? = null,
    val work: Work? = null,
    val chapters: List<Chapter> = emptyList(),
    val isBookmarked: Boolean = false,
    val lastReadChapter: Int = 0,
    val chaptersExpanded: Boolean = false,
    val checkingUpdate: Boolean = false,
    val updateMessage: String? = null,
    val bookmarkSaving: Boolean = false,
) {
    /** 开始阅读的章节号：上次阅读+1，否则第1话 */
    val startChapter: Int
        get() = if (lastReadChapter > 0) lastReadChapter else 1
}

@HiltViewModel
class DetailViewModel @Inject constructor(
    private val repository: ComicRepository,
    savedStateHandle: SavedStateHandle,
) : ViewModel() {

    private val _uiState = MutableStateFlow(DetailUiState())
    val uiState: StateFlow<DetailUiState> = _uiState.asStateFlow()

    private var currentWorkId: Long = 0L

    val workId: Long = savedStateHandle.get<Long>("workId") ?: 0L

    init {
        loadDetail(workId)
    }

    fun loadDetail(workId: Long) {
        if (workId == currentWorkId && _uiState.value.work != null) return
        currentWorkId = workId
        _uiState.value = DetailUiState(isLoading = true)
        viewModelScope.launch {
            runCatching {
                val detail = repository.getWorkDetail(workId)
                val bookmarks = runCatching { repository.getBookmarks() }.getOrDefault(emptyList())
                val bm = bookmarks.firstOrNull { it.workId == workId }
                DetailData(
                    work = detail.toWork(),
                    chapters = detail.chapters.sortedBy { it.chapterNum },
                    isBookmarked = bm != null,
                    lastReadChapter = bm?.chapterNum ?: 0,
                )
            }.onSuccess { data ->
                _uiState.value = _uiState.value.copy(
                    isLoading = false,
                    error = null,
                    work = data.work,
                    chapters = data.chapters,
                    isBookmarked = data.isBookmarked,
                    lastReadChapter = data.lastReadChapter,
                )
            }.onFailure { e ->
                _uiState.value = _uiState.value.copy(
                    isLoading = false,
                    error = e.message ?: "加载失败",
                )
            }
        }
    }

    fun toggleChaptersExpanded() {
        _uiState.value = _uiState.value.copy(chaptersExpanded = !_uiState.value.chaptersExpanded)
    }

    fun toggleShelf() {
        val work = _uiState.value.work ?: return
        val alreadyBookmarked = _uiState.value.isBookmarked
        _uiState.value = _uiState.value.copy(bookmarkSaving = true)
        viewModelScope.launch {
            if (alreadyBookmarked) {
                val ok = repository.deleteBookmark(work.id)
                _uiState.value = _uiState.value.copy(
                    bookmarkSaving = false,
                    isBookmarked = !ok,
                )
            } else {
                val ok = repository.saveBookmark(
                    workId = work.id,
                    chapterNum = _uiState.value.lastReadChapter,
                    note = "shelf",
                )
                _uiState.value = _uiState.value.copy(
                    bookmarkSaving = false,
                    isBookmarked = ok,
                )
            }
        }
    }

    fun setReadProgress(chapterNum: Int) {
        _uiState.value = _uiState.value.copy(lastReadChapter = chapterNum, bookmarkSaving = true)
        viewModelScope.launch {
            val ok = repository.saveBookmark(
                workId = currentWorkId,
                chapterNum = chapterNum,
                note = "shelf",
            )
            _uiState.value = _uiState.value.copy(bookmarkSaving = false, isBookmarked = ok || _uiState.value.isBookmarked)
        }
    }

    fun checkUpdate() {
        val work = _uiState.value.work ?: return
        _uiState.value = _uiState.value.copy(checkingUpdate = true, updateMessage = null)
        viewModelScope.launch {
            runCatching { repository.checkUpdate(work.id) }
                .onSuccess { msg ->
                    _uiState.value = _uiState.value.copy(
                        checkingUpdate = false,
                        updateMessage = msg.ifBlank { "检查完成" },
                    )
                }
                .onFailure { e ->
                    _uiState.value = _uiState.value.copy(
                        checkingUpdate = false,
                        updateMessage = e.message ?: "检查失败",
                    )
                }
        }
    }

    fun deleteWork() {
        viewModelScope.launch {
            val ok = repository.deleteWork(currentWorkId)
            if (!ok) {
                _uiState.value = _uiState.value.copy(updateMessage = "删除失败，请重试")
            }
        }
    }

    fun clearUpdateMessage() {
        _uiState.value = _uiState.value.copy(updateMessage = null)
    }

    private data class DetailData(
        val work: Work,
        val chapters: List<Chapter>,
        val isBookmarked: Boolean,
        val lastReadChapter: Int,
    )
}
