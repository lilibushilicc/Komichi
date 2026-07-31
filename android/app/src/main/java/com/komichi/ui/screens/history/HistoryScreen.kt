package com.komichi.ui.screens.history

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.aspectRatio
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.PlayArrow
import androidx.compose.material.icons.outlined.History
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.komichi.R
import com.komichi.ui.components.CoverImage
import com.komichi.ui.components.EmptyState
import com.komichi.ui.components.ErrorState
import com.komichi.ui.components.LoadingState
import com.komichi.ui.theme.CgCard
import com.komichi.ui.theme.CgSurfaceVariant
import com.komichi.util.formatRelative
import com.komichi.viewmodel.ShelfViewModel

@Composable
fun HistoryScreen(
    onOpenDetail: (Long) -> Unit,
    viewModel: ShelfViewModel = hiltViewModel(),
) {
    val state by viewModel.uiState.collectAsStateWithLifecycle()

    Column(
        modifier = Modifier
            .fillMaxSize()
            .statusBarsPadding(),
    ) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = 16.dp, vertical = 8.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Text(
                text = stringResource(R.string.history_title),
                style = MaterialTheme.typography.headlineMedium,
                fontWeight = FontWeight.Bold,
                color = MaterialTheme.colorScheme.onBackground,
            )
        }

        when {
            state.isLoading -> LoadingState(label = stringResource(R.string.common_loading))
            state.error != null -> ErrorState(message = state.error!!, onRetry = { viewModel.loadShelf() })
            state.items.isEmpty() -> EmptyState(
                icon = Icons.Outlined.History,
                title = stringResource(R.string.history_empty),
                subtitle = "阅读过的漫画会出现在这里",
            )
            else -> {
                LazyColumn(
                    modifier = Modifier.fillMaxSize(),
                    contentPadding = PaddingValues(16.dp),
                    verticalArrangement = Arrangement.spacedBy(12.dp),
                ) {
                    items(state.items, key = { it.work.id }) { item ->
                        HistoryItem(
                            title = item.work.title,
                            coverPath = item.work.coverR2Path,
                            lastChapter = item.lastChapter,
                            latestChapter = item.work.latestChapterNum,
                            lastReadTime = item.lastReadTime,
                            onClick = { onOpenDetail(item.work.id) },
                            onContinue = { onOpenDetail(item.work.id) },
                        )
                    }
                }
            }
        }
    }
}

@Composable
private fun HistoryItem(
    title: String,
    coverPath: String,
    lastChapter: Int,
    latestChapter: Int,
    lastReadTime: String,
    onClick: () -> Unit,
    onContinue: () -> Unit,
) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(12.dp))
            .background(CgCard)
            .clickable(onClick = onClick)
            .padding(12.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Box(
            modifier = Modifier
                .width(60.dp)
                .aspectRatio(3f / 4f)
                .clip(RoundedCornerShape(8.dp))
                .background(CgSurfaceVariant),
        ) {
            CoverImage(r2Path = coverPath, contentDescription = title, modifier = Modifier.fillMaxSize())
        }
        Spacer(Modifier.width(12.dp))
        Column(
            modifier = Modifier.weight(1f),
            verticalArrangement = Arrangement.spacedBy(4.dp),
        ) {
            Text(
                text = title.ifBlank { "未知标题" },
                style = MaterialTheme.typography.titleSmall,
                color = MaterialTheme.colorScheme.onSurface,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis,
            )
            val progress = if (lastChapter > 0) "读到 第${lastChapter}话" else "尚未开始"
            Text(
                text = progress,
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.primary,
            )
            val unread = latestChapter - lastChapter
            val extra = if (unread > 0) " · 待读 $unread 话" else " · 已读完"
            Text(
                text = "上次阅读：${formatRelative(lastReadTime)}$extra",
                style = MaterialTheme.typography.labelSmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis,
            )
        }
        IconButton(onClick = onContinue) {
            Icon(
                imageVector = Icons.Filled.PlayArrow,
                contentDescription = "继续阅读",
                tint = MaterialTheme.colorScheme.primary,
                modifier = Modifier.size(28.dp),
            )
        }
    }
}
