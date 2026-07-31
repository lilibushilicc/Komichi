package com.komichi.ui.screens.home

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material.icons.filled.Search
import androidx.compose.material.icons.outlined.SearchOff
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.OutlinedTextFieldDefaults
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.setValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.LifecycleEventObserver
import androidx.lifecycle.compose.LocalLifecycleOwner
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.komichi.R
import com.komichi.ui.components.ComicGridCard
import com.komichi.ui.components.EmptyState
import com.komichi.ui.components.ErrorState
import com.komichi.ui.components.LoadingState
import com.komichi.ui.components.SectionHeader
import com.komichi.viewmodel.ContinueItem
import com.komichi.viewmodel.HomeViewModel

@Composable
fun HomeScreen(
    onOpenDetail: (Long) -> Unit,
    viewModel: HomeViewModel = hiltViewModel(),
) {
    val state by viewModel.uiState.collectAsStateWithLifecycle()
    var firstResume by androidx.compose.runtime.remember { mutableStateOf(true) }
    val lifecycleOwner = LocalLifecycleOwner.current
    DisposableEffect(lifecycleOwner) {
        val observer = LifecycleEventObserver { _, event ->
            if (event == Lifecycle.Event.ON_RESUME) {
                if (firstResume) firstResume = false else viewModel.refresh()
            }
        }
        lifecycleOwner.lifecycle.addObserver(observer)
        onDispose { lifecycleOwner.lifecycle.removeObserver(observer) }
    }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .statusBarsPadding(),
    ) {
        // 顶部标题 + 刷新
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = 16.dp, vertical = 8.dp),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.SpaceBetween,
        ) {
            Text(
                text = stringResource(R.string.home_title),
                style = MaterialTheme.typography.headlineMedium,
                fontWeight = FontWeight.Bold,
                color = MaterialTheme.colorScheme.onBackground,
            )
            IconButton(onClick = { viewModel.refresh() }) {
                if (state.isRefreshing) {
                    CircularProgressIndicator(strokeWidth = 2.dp, modifier = Modifier.size(20.dp))
                } else {
                    Icon(Icons.Filled.Refresh, contentDescription = "刷新", tint = MaterialTheme.colorScheme.onSurfaceVariant)
                }
            }
        }

        // 搜索框
        OutlinedTextField(
            value = state.searchQuery,
            onValueChange = viewModel::setSearchQuery,
            placeholder = { Text(stringResource(R.string.home_search_hint)) },
            leadingIcon = { Icon(Icons.Filled.Search, null) },
            singleLine = true,
            shape = RoundedCornerShape(12.dp),
            colors = OutlinedTextFieldDefaults.colors(
                focusedTextColor = MaterialTheme.colorScheme.onSurface,
                unfocusedTextColor = MaterialTheme.colorScheme.onSurface,
                focusedBorderColor = MaterialTheme.colorScheme.primary,
                unfocusedBorderColor = MaterialTheme.colorScheme.outline,
                focusedContainerColor = MaterialTheme.colorScheme.surface,
                unfocusedContainerColor = MaterialTheme.colorScheme.surface,
                cursorColor = MaterialTheme.colorScheme.primary,
            ),
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = 16.dp, vertical = 4.dp),
        )

        when {
            state.isLoading -> LoadingState(label = stringResource(R.string.common_loading))
            state.error != null -> ErrorState(
                message = state.error!!,
                onRetry = { viewModel.loadHome() },
            )
            state.searchQuery.isNotBlank() -> SearchResults(
                results = state.searchResults,
                onOpenDetail = onOpenDetail,
            )
            else -> HomeContent(
                state = state,
                onOpenDetail = onOpenDetail,
            )
        }
    }
}

@Composable
private fun HomeContent(
    state: com.komichi.viewmodel.HomeUiState,
    onOpenDetail: (Long) -> Unit,
) {
    LazyColumn(
        modifier = Modifier.fillMaxSize(),
        contentPadding = PaddingValues(vertical = 8.dp),
        verticalArrangement = Arrangement.spacedBy(8.dp),
    ) {
        // 今日更新
        item {
            SectionHeader(title = stringResource(R.string.home_today_update))
        }
        if (state.todayUpdates.isEmpty()) {
            item {
                InlineEmpty(stringResource(R.string.home_no_today_update))
            }
        } else {
            item {
                LazyRow(
                    contentPadding = PaddingValues(horizontal = 16.dp),
                    horizontalArrangement = Arrangement.spacedBy(12.dp),
                ) {
                    items(state.todayUpdates, key = { it.id }) { work ->
                        ComicGridCard(
                            work = work,
                            onClick = { onOpenDetail(work.id) },
                            modifier = Modifier.width(130.dp),
                        )
                    }
                }
            }
        }

        // 继续阅读
        item {
            SectionHeader(title = stringResource(R.string.home_continue_reading))
        }
        if (state.continueReading.isEmpty()) {
            item { InlineEmpty(stringResource(R.string.home_no_reading)) }
        } else {
            item {
                LazyRow(
                    contentPadding = PaddingValues(horizontal = 16.dp),
                    horizontalArrangement = Arrangement.spacedBy(12.dp),
                ) {
                    items(state.continueReading, key = { it.work.id }) { item: ContinueItem ->
                        ComicGridCard(
                            work = item.work,
                            onClick = { onOpenDetail(item.work.id) },
                            modifier = Modifier.width(130.dp),
                        )
                    }
                }
            }
        }

        // 热门作品
        item {
            SectionHeader(title = stringResource(R.string.home_hot_works))
        }
        if (state.hotWorks.isEmpty()) {
            item { InlineEmpty(stringResource(R.string.common_empty)) }
        } else {
            item {
                LazyRow(
                    contentPadding = PaddingValues(horizontal = 16.dp),
                    horizontalArrangement = Arrangement.spacedBy(12.dp),
                ) {
                    items(state.hotWorks, key = { it.id }) { work ->
                        ComicGridCard(
                            work = work,
                            onClick = { onOpenDetail(work.id) },
                            modifier = Modifier.width(130.dp),
                        )
                    }
                }
            }
        }
        item { Spacer(Modifier.height(24.dp)) }
    }
}

@Composable
private fun SearchResults(
    results: List<com.komichi.data.Work>,
    onOpenDetail: (Long) -> Unit,
) {
    if (results.isEmpty()) {
        EmptyState(
            icon = Icons.Outlined.SearchOff,
            title = "未找到相关漫画",
            subtitle = "试试其他关键词",
        )
        return
    }
    LazyColumn(
        modifier = Modifier.fillMaxSize(),
        contentPadding = PaddingValues(16.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        items(results, key = { it.id }) { work ->
            com.komichi.ui.components.ComicListCard(
                work = work,
                onClick = { onOpenDetail(work.id) },
            )
        }
    }
}

@Composable
private fun InlineEmpty(text: String) {
    Box(
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = 16.dp, vertical = 12.dp),
    ) {
        Text(
            text = text,
            style = MaterialTheme.typography.bodyMedium,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
    }
}
