package com.komichi.viewmodel

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.komichi.repository.ComicRepository
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.launch
import javax.inject.Inject

data class AuthUiState(
    val isTesting: Boolean = false,
    val testResult: TestResult = TestResult.Idle,
    val isLoggingIn: Boolean = false,
    val loginError: String? = null,
    val loginSuccess: Boolean = false,
    val savedWorkerUrl: String = "",
    val savedUsername: String = "",
)

sealed interface TestResult {
    data object Idle : TestResult
    data object Testing : TestResult
    data class Ok(val message: String) : TestResult
    data class Fail(val message: String) : TestResult
}

@HiltViewModel
class AuthViewModel @Inject constructor(
    private val repository: ComicRepository,
) : ViewModel() {

    val isLoggedIn: StateFlow<Boolean> = repository.storeManager().isLoggedIn
        .stateIn(viewModelScope, SharingStarted.Eagerly, false)

    private val _uiState = MutableStateFlow(AuthUiState())
    val uiState: StateFlow<AuthUiState> = _uiState.asStateFlow()

    init {
        loadSavedConfig()
    }

    private fun loadSavedConfig() {
        viewModelScope.launch {
            val url = repository.currentWorkerUrl()
            val name = repository.currentUsername()
            _uiState.value = _uiState.value.copy(savedWorkerUrl = url, savedUsername = name)
        }
    }

    fun testConnection(workerUrl: String) {
        if (workerUrl.isBlank()) {
            _uiState.value = _uiState.value.copy(testResult = TestResult.Fail("请输入服务器地址"))
            return
        }
        _uiState.value = _uiState.value.copy(isTesting = true, testResult = TestResult.Testing)
        viewModelScope.launch {
            val ok = runCatching { repository.testConnection(workerUrl) }.getOrDefault(false)
            _uiState.value = _uiState.value.copy(
                isTesting = false,
                testResult = if (ok) TestResult.Ok("连接成功") else TestResult.Fail("无法连接服务器"),
            )
        }
    }

    fun login(username: String, password: String, workerUrl: String) {
        when {
            workerUrl.isBlank() -> {
                _uiState.value = _uiState.value.copy(loginError = "请输入服务器地址")
            }
            username.isBlank() -> {
                _uiState.value = _uiState.value.copy(loginError = "请输入用户名")
            }
            password.isBlank() -> {
                _uiState.value = _uiState.value.copy(loginError = "请输入密码")
            }
            else -> {
                _uiState.value = _uiState.value.copy(
                    isLoggingIn = true, loginError = null, loginSuccess = false,
                )
                viewModelScope.launch {
                    runCatching { repository.login(username, password, workerUrl) }
                        .onSuccess {
                            _uiState.value = _uiState.value.copy(
                                isLoggingIn = false, loginSuccess = true, loginError = null,
                            )
                        }
                        .onFailure { e ->
                            _uiState.value = _uiState.value.copy(
                                isLoggingIn = false,
                                loginError = e.message ?: "登录失败",
                            )
                        }
                }
            }
        }
    }

    fun clearTestResult() {
        _uiState.value = _uiState.value.copy(testResult = TestResult.Idle)
    }

    fun clearLoginError() {
        _uiState.value = _uiState.value.copy(loginError = null)
    }

    fun logout() {
        viewModelScope.launch { repository.logout() }
    }
}
