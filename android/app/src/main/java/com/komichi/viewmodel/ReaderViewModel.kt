package com.komichi.viewmodel

import androidx.lifecycle.SavedStateHandle
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.komichi.data.Chapter
import com.komichi.repository.ComicRepository
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import javax.inject.Inject

data class ReaderUiState(
    val isLoading: Boolean = true,
    val error: String? = null,
    val workTitle: String = "",
    val chapters: List<Chapter> = emptyList(),
    val currentIndex: Int = 0,
) {
    val currentChapter: Chapter? get() = chapters.getOrNull(currentIndex)
}

@HiltViewModel
class ReaderViewModel @Inject constructor(
    private val repository: ComicRepository,
    savedStateHandle: SavedStateHandle,
) : ViewModel() {

    private val _uiState = MutableStateFlow(ReaderUiState())
    val uiState: StateFlow<ReaderUiState> = _uiState.asStateFlow()

    private val workId: Long = savedStateHandle.get<Long>("workId") ?: 0L
    private val startChapterNum: Int = savedStateHandle.get<Int>("chapterNum") ?: 1

    init {
        load(workId, startChapterNum)
    }

    fun load(workId: Long, chapterNum: Int) {
        viewModelScope.launch {
            runCatching {
                val detail = repository.getWorkDetail(workId)
                val chapters = detail.chapters.sortedBy { it.chapterNum }
                val index = chapters.indexOfFirst { it.chapterNum == chapterNum }
                    .takeIf { it >= 0 } ?: chapters.indices.firstOrNull() ?: 0
                ReaderData(detail.title, chapters, index)
            }.onSuccess { data ->
                _uiState.value = _uiState.value.copy(
                    isLoading = false,
                    error = null,
                    workTitle = data.title,
                    chapters = data.chapters,
                    currentIndex = data.index,
                )
                saveProgress()
            }.onFailure { e ->
                _uiState.value = _uiState.value.copy(
                    isLoading = false,
                    error = e.message ?: "加载失败",
                )
            }
        }
    }

    fun retry() = load(workId, startChapterNum)

    fun openChapter(index: Int) {
        val chapters = _uiState.value.chapters
        if (index < 0 || index >= chapters.size) return
        _uiState.value = _uiState.value.copy(currentIndex = index)
        saveProgress()
    }

    private fun saveProgress() {
        val chapter = _uiState.value.currentChapter ?: return
        viewModelScope.launch {
            repository.saveBookmark(workId, chapter.chapterNum, note = "reader")
        }
    }

    private data class ReaderData(
        val title: String,
        val chapters: List<Chapter>,
        val index: Int,
    )
}
