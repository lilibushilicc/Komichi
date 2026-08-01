@file:OptIn(androidx.compose.material3.ExperimentalMaterial3Api::class)

package com.komichi.ui.screens.detail

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.aspectRatio
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.Bookmark
import androidx.compose.material.icons.filled.BookmarkBorder
import androidx.compose.material.icons.filled.Delete
import androidx.compose.material.icons.filled.ExpandLess
import androidx.compose.material.icons.filled.ExpandMore
import androidx.compose.material.icons.filled.MoreVert
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.TextButton
import androidx.compose.material3.Scaffold
import androidx.compose.material3.SnackbarHost
import androidx.compose.material3.SnackbarHostState
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.TopAppBarDefaults
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.komichi.R
import com.komichi.data.WorkStatus
import com.komichi.ui.components.CoverImage
import com.komichi.ui.components.ErrorState
import com.komichi.ui.components.LoadingState
import com.komichi.ui.components.StatusBadge
import com.komichi.ui.theme.CgCard
import com.komichi.ui.theme.CgSurfaceVariant
import com.komichi.util.formatDate
import com.komichi.util.formatSourceName
import com.komichi.viewmodel.DetailViewModel

@Composable
fun DetailScreen(
    onBack: () -> Unit,
    onOpenReader: (Int) -> Unit,
    onWorkDeleted: () -> Unit = onBack,
    viewModel: DetailViewModel = hiltViewModel(),
) {
    val state by viewModel.uiState.collectAsStateWithLifecycle()
    val snackbarHostState = remember { SnackbarHostState() }
    var showMenu by remember { mutableStateOf(false) }
    var showDeleteDialog by remember { mutableStateOf(false) }

    LaunchedEffect(state.updateMessage) {
        state.updateMessage?.let {
            snackbarHostState.showSnackbar(it)
            viewModel.clearUpdateMessage()
        }
    }

    if (showDeleteDialog) {
        AlertDialog(
            onDismissRequest = { showDeleteDialog = false },
            title = { Text("确认删除") },
            text = { Text("确定要删除「${state.work?.title}」吗？\n作品及所有章节将被永久删除，不可恢复。") },
            confirmButton = {
                TextButton(onClick = {
                    showDeleteDialog = false
                    viewModel.deleteWork()
                    onWorkDeleted()
                }) {
                    Text("删除", color = MaterialTheme.colorScheme.error)
                }
            },
            dismissButton = {
                TextButton(onClick = { showDeleteDialog = false }) {
                    Text("取消")
                }
            },
        )
    }

    Scaffold(
        containerColor = MaterialTheme.colorScheme.background,
        topBar = {
            TopAppBar(
                title = {
                    Text(
                        text = state.work?.title ?: "作品详情",
                        style = MaterialTheme.typography.titleMedium,
                        maxLines = 1,
                        overflow = TextOverflow.Ellipsis,
                    )
                },
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = "返回")
                    }
                },
                actions = {
                    Box {
                        IconButton(onClick = { showMenu = true }) {
                            Icon(Icons.Filled.MoreVert, contentDescription = "更多")
                        }
                        DropdownMenu(expanded = showMenu, onDismissRequest = { showMenu = false }) {
                            DropdownMenuItem(
                                text = { Text("删除作品", color = MaterialTheme.colorScheme.error) },
                                onClick = {
                                    showMenu = false
                                    showDeleteDialog = true
                                },
                                leadingIcon = {
                                    Icon(Icons.Filled.Delete, null, tint = MaterialTheme.colorScheme.error)
                                },
                            )
                        }
                    }
                },
                colors = TopAppBarDefaults.topAppBarColors(
                    containerColor = MaterialTheme.colorScheme.background,
                    titleContentColor = MaterialTheme.colorScheme.onBackground,
                    navigationIconContentColor = MaterialTheme.colorScheme.onBackground,
                ),
            )
        },
        snackbarHost = { SnackbarHost(snackbarHostState) },
    ) { padding ->
        when {
            state.isLoading -> LoadingState(modifier = Modifier.padding(padding))
            state.error != null -> ErrorState(
                message = state.error!!,
                onRetry = { viewModel.loadDetail(viewModel.workId) },
                modifier = Modifier.padding(padding),
            )
            state.work != null -> DetailContent(
                state = state,
                onToggleShelf = viewModel::toggleShelf,
                onCheckUpdate = viewModel::checkUpdate,
                onToggleExpand = viewModel::toggleChaptersExpanded,
                onSetReadProgress = viewModel::setReadProgress,
                onOpenReader = onOpenReader,
                modifier = Modifier.padding(padding),
            )
        }
    }
}

@Composable
private fun DetailContent(
    state: com.komichi.viewmodel.DetailUiState,
    onToggleShelf: () -> Unit,
    onCheckUpdate: () -> Unit,
    onToggleExpand: () -> Unit,
    onSetReadProgress: (Int) -> Unit,
    onOpenReader: (Int) -> Unit,
    modifier: Modifier = Modifier,
) {
    val work = state.work ?: return
    LazyColumn(
        modifier = modifier.fillMaxSize(),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        // 头部：封面 + 信息
        item {
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(16.dp),
            ) {
                Box(
                    modifier = Modifier
                        .width(120.dp)
                        .aspectRatio(3f / 4f)
                        .clip(RoundedCornerShape(12.dp))
                        .background(CgSurfaceVariant),
                ) {
                    CoverImage(r2Path = work.coverR2Path, contentDescription = work.title, modifier = Modifier.fillMaxSize())
                }
                Spacer(Modifier.width(16.dp))
                Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                    Text(
                        text = work.title.ifBlank { "未知标题" },
                        style = MaterialTheme.typography.titleLarge,
                        fontWeight = FontWeight.Bold,
                        color = MaterialTheme.colorScheme.onBackground,
                        maxLines = 2,
                        overflow = TextOverflow.Ellipsis,
                    )
                    InfoLine(stringResource(R.string.detail_category), work.category.ifBlank { "未分类" })
                    InfoLine(
                        stringResource(R.string.detail_status),
                        stringResource(if (WorkStatus.isOngoing(work.status)) R.string.common_status_ongoing else R.string.common_status_completed),
                    )
                    InfoLine(stringResource(R.string.detail_latest_chapter), "第${work.latestChapterNum}话")
                    if (state.lastReadChapter > 0) {
                        InfoLine(stringResource(R.string.detail_last_read), "第${state.lastReadChapter}话")
                    }
                    InfoLine("更新时间", formatDate(work.updateTime.ifBlank { work.createTime }))
                    InfoLine("数据来源", formatSourceName(work.source))
                    InfoLine(
                        "自动刷新",
                        if (work.autoRefresh) "支持（Worker 定时）" else "不支持（需PC更新）",
                    )
                }
            }
        }

        // 操作按钮
        item {
            OutlinedButton(
                onClick = onToggleShelf,
                shape = RoundedCornerShape(12.dp),
                enabled = !state.bookmarkSaving,
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(horizontal = 16.dp),
            ) {
                Icon(
                    if (state.isBookmarked) Icons.Filled.Bookmark else Icons.Filled.BookmarkBorder,
                    null,
                    modifier = Modifier.size(18.dp),
                )
                Spacer(Modifier.width(4.dp))
                Text(if (state.isBookmarked) "已在书架" else stringResource(R.string.detail_add_shelf))
            }
        }

        item {
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(horizontal = 16.dp),
            ) {
                OutlinedButton(
                    onClick = onCheckUpdate,
                    shape = RoundedCornerShape(12.dp),
                    enabled = !state.checkingUpdate,
                    modifier = Modifier.fillMaxWidth(),
                ) {
                    if (state.checkingUpdate) {
                        CircularProgressIndicator(strokeWidth = 2.dp, modifier = Modifier.size(16.dp))
                        Spacer(Modifier.width(8.dp))
                    } else {
                        Icon(Icons.Filled.Refresh, null, modifier = Modifier.size(18.dp))
                        Spacer(Modifier.width(8.dp))
                    }
                    Text(stringResource(R.string.detail_check_update))
                }
            }
        }

        // 简介
        val intro = work.summary.ifBlank { work.description }
        if (intro.isNotBlank()) {
            item {
                Column(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(horizontal = 16.dp)
                        .clip(RoundedCornerShape(12.dp))
                        .background(CgCard)
                        .padding(16.dp),
                ) {
                    Text(
                        text = stringResource(R.string.detail_summary),
                        style = MaterialTheme.typography.titleSmall,
                        fontWeight = FontWeight.Bold,
                        color = MaterialTheme.colorScheme.primary,
                    )
                    Spacer(Modifier.size(8.dp))
                    Text(
                        text = intro,
                        style = MaterialTheme.typography.bodyMedium,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
            }
        }

        // 章节列表
        item {
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .clickable(onClick = onToggleExpand)
                    .padding(horizontal = 16.dp, vertical = 8.dp),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Text(
                    text = "${stringResource(R.string.detail_chapters)}（${state.chapters.size}）",
                    style = MaterialTheme.typography.titleMedium,
                    fontWeight = FontWeight.Bold,
                    color = MaterialTheme.colorScheme.onBackground,
                )
                Icon(
                    if (state.chaptersExpanded) Icons.Filled.ExpandLess else Icons.Filled.ExpandMore,
                    null,
                    tint = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
        }

        val visibleChapters = if (state.chaptersExpanded) state.chapters else state.chapters.take(8)
        items(visibleChapters, key = { it.id }) { chapter ->
            val isRead = state.lastReadChapter >= chapter.chapterNum
            val isCurrent = state.lastReadChapter == chapter.chapterNum
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .clickable { onSetReadProgress(chapter.chapterNum) }
                    .padding(horizontal = 16.dp, vertical = 12.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Text(
                    text = "第${chapter.chapterNum}话",
                    style = MaterialTheme.typography.bodyMedium,
                    color = if (isRead) MaterialTheme.colorScheme.onSurfaceVariant else MaterialTheme.colorScheme.onSurface,
                    modifier = Modifier.weight(1f),
                )
                if (isCurrent) {
                    StatusBadge(status = WorkStatus.COMPLETED, modifier = Modifier.padding(end = 4.dp))
                }
                Text(
                    text = if (isCurrent) "当前" else if (isRead) "已读" else "未读",
                    style = MaterialTheme.typography.labelSmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
        }

        if (!state.chaptersExpanded && state.chapters.size > 8) {
            item {
                TextButton(
                    onClick = onToggleExpand,
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(vertical = 4.dp),
                ) {
                    Icon(Icons.Filled.ExpandMore, null, modifier = Modifier.size(18.dp))
                    Spacer(Modifier.width(4.dp))
                    Text("展开全部 ${state.chapters.size} 话", color = MaterialTheme.colorScheme.primary)
                }
            }
        }

        if (state.chaptersExpanded && state.chapters.size > 8) {
            item {
                TextButton(
                    onClick = onToggleExpand,
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(vertical = 4.dp),
                ) {
                    Icon(Icons.Filled.ExpandLess, null, modifier = Modifier.size(18.dp))
                    Spacer(Modifier.width(4.dp))
                    Text("收起", color = MaterialTheme.colorScheme.primary)
                }
            }
        }

        if (state.chapters.isEmpty()) {
            item {
                Text(
                    text = stringResource(R.string.detail_no_chapters),
                    style = MaterialTheme.typography.bodyMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    modifier = Modifier.padding(16.dp),
                )
            }
        }
        item { Spacer(Modifier.height(24.dp)) }
    }
}

@Composable
private fun InfoLine(label: String, value: String) {
    Row(verticalAlignment = Alignment.CenterVertically) {
        Text(
            text = "$label：",
            style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
        Text(
            text = value,
            style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.onSurface,
            maxLines = 1,
            overflow = TextOverflow.Ellipsis,
        )
    }
}
