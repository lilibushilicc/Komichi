package com.komichi.ui.screens.home

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
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
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material.icons.filled.Search
import androidx.compose.material.icons.outlined.SearchOff
import androidx.compose.material.icons.outlined.TravelExplore
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.OutlinedTextFieldDefaults
import androidx.compose.material3.SnackbarHost
import androidx.compose.material3.SnackbarHostState
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.setValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.LifecycleEventObserver
import androidx.lifecycle.compose.LocalLifecycleOwner
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.input.KeyboardCapitalization
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.komichi.R
import com.komichi.api.SourceSearchItem
import com.komichi.ui.components.ComicGridCard
import com.komichi.ui.components.EmptyState
import com.komichi.ui.components.ErrorState
import com.komichi.ui.components.LoadingState
import com.komichi.ui.components.SectionHeader
import com.komichi.viewmodel.ContinueItem
import com.komichi.viewmodel.HomeViewModel
import com.komichi.viewmodel.SearchMode

@Composable
fun HomeScreen(
    onOpenDetail: (Long) -> Unit,
    viewModel: HomeViewModel = hiltViewModel(),
) {
    val state by viewModel.uiState.collectAsStateWithLifecycle()
    var firstResume by remember { mutableStateOf(true) }
    val lifecycleOwner = LocalLifecycleOwner.current
    val snackbarHostState = remember { SnackbarHostState() }

    // 导入结果用 Snackbar 提示
    LaunchedEffect(state.importMessage) {
        state.importMessage?.let {
            snackbarHostState.showSnackbar(it)
            viewModel.clearImportMessage()
        }
    }

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

        // 搜索模式切换 Tab
        SearchModeTabs(
            selectedMode = state.searchMode,
            onModeChange = viewModel::setSearchMode,
        )

        // 搜索框
        SearchField(
            query = state.searchQuery,
            mode = state.searchMode,
            isSearching = state.isSearching,
            onQueryChange = viewModel::setSearchQuery,
            onSearch = { viewModel.searchSourceWorks(state.searchQuery) },
        )

        // 内容区
        Box(modifier = Modifier.fillMaxSize()) {
            when (state.searchMode) {
                SearchMode.LOCAL -> {
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
                SearchMode.SOURCE -> {
                    SourceSearchContent(
                        state = state,
                        onImport = viewModel::importFromSource,
                        onRetry = { viewModel.searchSourceWorks(state.searchQuery) },
                    )
                }
            }
            SnackbarHost(
                hostState = snackbarHostState,
                modifier = Modifier.align(Alignment.BottomCenter),
            )
        }
    }
}

// ============================================================
// 搜索模式 Tab
// ============================================================
@Composable
private fun SearchModeTabs(
    selectedMode: SearchMode,
    onModeChange: (SearchMode) -> Unit,
) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = 16.dp, vertical = 4.dp),
        horizontalArrangement = Arrangement.spacedBy(8.dp),
    ) {
        SearchTab(
            text = "本地搜索",
            selected = selectedMode == SearchMode.LOCAL,
            onClick = { onModeChange(SearchMode.LOCAL) },
            modifier = Modifier.weight(1f),
        )
        SearchTab(
            text = "源站搜索",
            selected = selectedMode == SearchMode.SOURCE,
            onClick = { onModeChange(SearchMode.SOURCE) },
            modifier = Modifier.weight(1f),
        )
    }
}

@Composable
private fun SearchTab(
    text: String,
    selected: Boolean,
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
) {
    val bg = if (selected) MaterialTheme.colorScheme.primaryContainer
    else MaterialTheme.colorScheme.surface
    val fg = if (selected) MaterialTheme.colorScheme.onPrimaryContainer
    else MaterialTheme.colorScheme.onSurfaceVariant

    Box(
        modifier = modifier
            .clip(RoundedCornerShape(10.dp))
            .background(bg)
            .clickable(onClick = onClick)
            .padding(vertical = 8.dp),
        contentAlignment = Alignment.Center,
    ) {
        Text(
            text = text,
            style = MaterialTheme.typography.labelLarge,
            fontWeight = if (selected) FontWeight.SemiBold else FontWeight.Normal,
            color = fg,
        )
    }
}

// ============================================================
// 搜索框
// ============================================================
@Composable
private fun SearchField(
    query: String,
    mode: SearchMode,
    isSearching: Boolean,
    onQueryChange: (String) -> Unit,
    onSearch: () -> Unit,
) {
    val keyboardOptions = androidx.compose.foundation.text.KeyboardOptions(
        imeAction = if (mode == SearchMode.SOURCE) ImeAction.Search else ImeAction.Done,
        capitalization = KeyboardCapitalization.None,
    )
    val keyboardActions = androidx.compose.foundation.text.KeyboardActions(
        onSearch = { onSearch() },
    )

    OutlinedTextField(
        value = query,
        onValueChange = onQueryChange,
        placeholder = {
            Text(
                if (mode == SearchMode.SOURCE) "输入漫画名搜索源站"
                else stringResource(R.string.home_search_hint)
            )
        },
        leadingIcon = { Icon(Icons.Filled.Search, null) },
        trailingIcon = {
            if (mode == SearchMode.SOURCE) {
                if (isSearching) {
                    CircularProgressIndicator(
                        strokeWidth = 2.dp,
                        modifier = Modifier.size(20.dp),
                    )
                } else if (query.isNotBlank()) {
                    IconButton(onClick = onSearch) {
                        Icon(
                            Icons.Outlined.TravelExplore,
                            contentDescription = "搜索源站",
                            tint = MaterialTheme.colorScheme.primary,
                        )
                    }
                }
            }
        },
        singleLine = true,
        keyboardOptions = keyboardOptions,
        keyboardActions = keyboardActions,
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
}

// ============================================================
// 源站搜索结果
// ============================================================
@Composable
private fun SourceSearchContent(
    state: com.komichi.viewmodel.HomeUiState,
    onImport: (String) -> Unit,
    onRetry: () -> Unit,
) {
    when {
        state.isSearching -> LoadingState(label = "正在搜索源站...")
        state.searchError != null -> ErrorState(
            message = state.searchError!!,
            onRetry = onRetry,
        )
        state.sourceSearchResults.isNotEmpty() -> SourceSearchResults(
            results = state.sourceSearchResults,
            importingUrl = state.importingUrl,
            onImport = onImport,
        )
        else -> EmptyState(
            icon = Icons.Outlined.TravelExplore,
            title = "搜索源站漫画",
            subtitle = "输入漫画名，从哔哩哔哩、咕哒等源站搜索\n找到后可直接导入",
        )
    }
}

@Composable
private fun SourceSearchResults(
    results: Map<String, List<SourceSearchItem>>,
    importingUrl: String?,
    onImport: (String) -> Unit,
) {
    LazyColumn(
        modifier = Modifier.fillMaxSize(),
        contentPadding = PaddingValues(horizontal = 16.dp, vertical = 8.dp),
        verticalArrangement = Arrangement.spacedBy(8.dp),
    ) {
        results.forEach { (source, items) ->
            if (items.isNotEmpty()) {
                item(key = "header-$source") {
                    SourceHeader(source)
                }
                items(items, key = { "$source-${it.url}" }) { item ->
                    SourceResultItem(
                        item = item,
                        isImporting = importingUrl == item.url,
                        onImport = { onImport(item.url) },
                    )
                }
            }
        }
        item { Spacer(Modifier.height(24.dp)) }
    }
}

@Composable
private fun SourceHeader(source: String) {
    Text(
        text = sourceDisplayName(source),
        style = MaterialTheme.typography.titleSmall,
        fontWeight = FontWeight.Bold,
        color = MaterialTheme.colorScheme.primary,
        modifier = Modifier.padding(top = 8.dp, bottom = 2.dp),
    )
}

@Composable
private fun SourceResultItem(
    item: SourceSearchItem,
    isImporting: Boolean,
    onImport: () -> Unit,
) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(10.dp))
            .background(MaterialTheme.colorScheme.surface)
            .padding(horizontal = 12.dp, vertical = 10.dp),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.SpaceBetween,
    ) {
        Text(
            text = item.title,
            style = MaterialTheme.typography.bodyMedium,
            color = MaterialTheme.colorScheme.onSurface,
            modifier = Modifier.weight(1f, fill = true),
            maxLines = 2,
        )
        Spacer(Modifier.width(8.dp))
        OutlinedButton(
            onClick = onImport,
            enabled = !isImporting,
            contentPadding = PaddingValues(horizontal = 12.dp, vertical = 4.dp),
            modifier = Modifier.height(36.dp),
        ) {
            if (isImporting) {
                CircularProgressIndicator(
                    strokeWidth = 2.dp,
                    modifier = Modifier.size(16.dp),
                )
            } else {
                Icon(
                    Icons.Filled.Add,
                    contentDescription = null,
                    modifier = Modifier.size(16.dp),
                )
                Spacer(Modifier.width(4.dp))
                Text("导入", style = MaterialTheme.typography.labelMedium)
            }
        }
    }
}

/** 源标识 -> 中文展示名 */
private fun sourceDisplayName(source: String): String = when (source.lowercase()) {
    "bilibili" -> "哔哩哔哩漫画"
    "godamh" -> "GoDa漫画"
    "mh160mh" -> "漫画160"
    "tencent" -> "腾讯动漫"
    "guazi" -> "瓜子漫画"
    "kuaikan" -> "快看漫画"
    "sfacg" -> "SF漫画"
    "dongmanmanhua" -> "东漫漫画"
    "18comic" -> "禁漫天堂"
    else -> source
}

// ============================================================
// 本地搜索结果 & 首页内容（原有逻辑）
// ============================================================
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
