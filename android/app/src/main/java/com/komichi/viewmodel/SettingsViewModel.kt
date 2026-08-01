@file:OptIn(coil.annotation.ExperimentalCoilApi::class)

package com.komichi.viewmodel

import android.content.Context
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import coil.imageLoader
import com.komichi.data.SourceConfig
import com.komichi.data.StoreManager
import com.komichi.repository.ComicRepository
import dagger.hilt.android.lifecycle.HiltViewModel
import dagger.hilt.android.qualifiers.ApplicationContext
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import org.json.JSONObject
import java.io.File
import javax.inject.Inject

/** 单个源的状态（用于 UI 显示） */
data class SourceState(
    val name: String,
    val displayName: String,
    val enabled: Boolean,
)

data class SettingsUiState(
    val username: String = "",
    val workerUrl: String = "",
    val tokenMasked: String = "",
    val isLoggingOut: Boolean = false,
    val message: String? = null,
    val sources: List<SourceState> = emptyList(),
)

@HiltViewModel
class SettingsViewModel @Inject constructor(
    @ApplicationContext private val context: Context,
    private val repository: ComicRepository,
    private val storeManager: StoreManager,
) : ViewModel() {

    private val _uiState = MutableStateFlow(SettingsUiState())
    val uiState: StateFlow<SettingsUiState> = _uiState.asStateFlow()

    init {
        loadConfig()
    }

    private fun loadConfig() {
        viewModelScope.launch {
            val url = storeManager.workerUrl.first()
            val name = storeManager.username.first()
            val token = storeManager.token.first()
            val disabled = storeManager.disabledSources.first()
            _uiState.value = _uiState.value.copy(
                username = name,
                workerUrl = url,
                tokenMasked = maskToken(token),
                sources = SourceConfig.ALL_SOURCES.map { info ->
                    SourceState(
                        name = info.name,
                        displayName = info.displayName,
                        enabled = info.name !in disabled,
                    )
                },
            )
        }
    }

    fun saveWorkerUrl(url: String) {
        viewModelScope.launch {
            storeManager.saveWorkerUrl(url)
            repository.refreshConfig()
            _uiState.value = _uiState.value.copy(workerUrl = url, message = "服务器地址已保存")
        }
    }

    /** 切换源的启用/禁用状态 */
    fun toggleSource(name: String) {
        viewModelScope.launch {
            val current = _uiState.value.sources.find { it.name == name } ?: return@launch
            val newEnabled = !current.enabled
            storeManager.setSourceEnabled(name, newEnabled)
            _uiState.value = _uiState.value.copy(
                sources = _uiState.value.sources.map {
                    if (it.name == name) it.copy(enabled = newEnabled) else it
                },
                message = "${current.displayName} 已${if (newEnabled) "启用" else "禁用"}",
            )
        }
    }

    fun clearCache() {
        viewModelScope.launch {
            val loader = context.imageLoader
            loader.memoryCache?.clear()
            withContext(Dispatchers.IO) {
                loader.diskCache?.clear()
            }
            _uiState.value = _uiState.value.copy(message = "缓存已清除")
        }
    }

    fun backupData() {
        viewModelScope.launch {
            val result = runCatching {
                val json = JSONObject().apply {
                    put("worker_url", storeManager.workerUrl.first())
                    put("username", storeManager.username.first())
                    put("backup_time", System.currentTimeMillis())
                }
                val dir = File(context.getExternalFilesDir(null) ?: context.filesDir, "backup")
                if (!dir.exists()) dir.mkdirs()
                val file = File(dir, "komichi_backup.json")
                withContext(Dispatchers.IO) {
                    file.writeText(json.toString(2))
                }
                "已备份至：${file.absolutePath}"
            }
            _uiState.value = _uiState.value.copy(
                message = result.getOrElse { "备份失败：${it.message}" },
            )
        }
    }

    fun logout() {
        _uiState.value = _uiState.value.copy(isLoggingOut = true)
        viewModelScope.launch {
            repository.logout()
            _uiState.value = _uiState.value.copy(isLoggingOut = false)
        }
    }

    fun clearMessage() {
        _uiState.value = _uiState.value.copy(message = null)
    }

    private fun maskToken(token: String): String {
        if (token.isBlank()) return ""
        return if (token.length <= 8) {
            "*".repeat(token.length)
        } else {
            token.take(4) + "****" + token.takeLast(4)
        }
    }
}
