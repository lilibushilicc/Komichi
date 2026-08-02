package com.komichi.viewmodel

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.komichi.data.StoreManager
import com.komichi.ui.theme.KomichiPalette
import com.komichi.ui.theme.ThemeMode
import com.komichi.ui.theme.paletteById
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.map
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.launch
import javax.inject.Inject

/**
 * 主题状态：当前配色与明暗模式。
 * 单一事实来源为 StoreManager（DataStore）。MainActivity 与 SettingsScreen 各自持有
 * 本 VM 实例，但都观察同一份持久化数据，切换即时生效。
 */
@HiltViewModel
class ThemeViewModel @Inject constructor(
    private val storeManager: StoreManager,
) : ViewModel() {

    val palette: StateFlow<KomichiPalette> = storeManager.themePalette
        .map { paletteById(it) }
        .stateIn(
            scope = viewModelScope,
            started = SharingStarted.WhileSubscribed(5000),
            initialValue = paletteById("mint"),
        )

    val themeMode: StateFlow<ThemeMode> = storeManager.themeMode
        .map { ThemeMode.fromId(it) }
        .stateIn(
            scope = viewModelScope,
            started = SharingStarted.WhileSubscribed(5000),
            initialValue = ThemeMode.SYSTEM,
        )

    fun setPalette(id: String) {
        viewModelScope.launch { storeManager.saveThemePalette(id) }
    }

    fun setThemeMode(mode: ThemeMode) {
        viewModelScope.launch { storeManager.saveThemeMode(mode.id) }
    }
}
