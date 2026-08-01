package com.komichi.ui.components

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
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.outlined.BrokenImage
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import coil.compose.SubcomposeAsyncImage
import coil.request.ImageRequest
import com.komichi.data.Work
import com.komichi.data.WorkStatus
import com.komichi.ui.theme.CgCard
import com.komichi.ui.theme.CgOutline
import com.komichi.ui.theme.CgStatusCompleted
import com.komichi.ui.theme.CgStatusOngoing
import com.komichi.ui.theme.CgSurfaceVariant
import com.komichi.util.formatRelative
import com.komichi.util.formatSourceName
import com.komichi.util.isToday

/** 封面图片：自动经 R2 签名加载，带骨架与错误占位 */
@Composable
fun CoverImage(
    r2Path: String?,
    contentDescription: String?,
    modifier: Modifier = Modifier,
    contentScale: ContentScale = ContentScale.Crop,
) {
    val context = LocalContext.current
    SubcomposeAsyncImage(
        model = ImageRequest.Builder(context)
            .data(r2Path?.takeIf { it.isNotBlank() })
            .crossfade(true)
            .build(),
        contentDescription = contentDescription,
        contentScale = contentScale,
        modifier = modifier,
        loading = {
            Box(Modifier.fillMaxSize().background(CgSurfaceVariant)) {
                ShimmerBox(Modifier.fillMaxSize(), cornerRadius = 0.dp)
            }
        },
        error = {
            Box(
                Modifier.fillMaxSize().background(CgSurfaceVariant),
                contentAlignment = Alignment.Center,
            ) {
                Icon(
                    imageVector = Icons.Outlined.BrokenImage,
                    contentDescription = null,
                    tint = CgOutline,
                )
            }
        },
    )
}

/** 状态徽标：连载中 / 已完结 */
@Composable
fun StatusBadge(status: Int, modifier: Modifier = Modifier) {
    val (text, color) = if (WorkStatus.isOngoing(status)) {
        "连载" to CgStatusOngoing
    } else {
        "完结" to CgStatusCompleted
    }
    Box(
        modifier = modifier
            .clip(RoundedCornerShape(6.dp))
            .background(color.copy(alpha = 0.85f))
            .padding(horizontal = 6.dp, vertical = 2.dp),
    ) {
        Text(
            text = text,
            style = MaterialTheme.typography.labelSmall,
            color = MaterialTheme.colorScheme.onPrimary,
            fontWeight = FontWeight.SemiBold,
        )
    }
}

/** 今日更新小红点 */
@Composable
private fun UpdateDot(modifier: Modifier = Modifier) {
    Box(
        modifier = modifier
            .size(8.dp)
            .clip(RoundedCornerShape(4.dp))
            .background(CgStatusOngoing),
    )
}

/** 网格模式漫画卡片：封面(3:4) + 标题 + 最新章节 */
@Composable
fun ComicGridCard(
    work: Work,
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
) {
    Column(
        modifier = modifier.clickable(onClick = onClick),
    ) {
        Box(
            modifier = Modifier
                .fillMaxWidth()
                .aspectRatio(3f / 4f)
                .clip(RoundedCornerShape(12.dp))
                .background(CgCard),
        ) {
            CoverImage(
                r2Path = work.coverR2Path,
                contentDescription = work.title,
                modifier = Modifier.fillMaxSize(),
            )
            StatusBadge(
                status = work.status,
                modifier = Modifier
                    .align(Alignment.TopStart)
                    .padding(6.dp),
            )
            if (isToday(work.updateTime) || isToday(work.createTime)) {
                UpdateDot(
                    Modifier
                        .align(Alignment.TopEnd)
                        .padding(6.dp),
                )
            }
        }
        Text(
            text = work.title.ifBlank { "未知标题" },
            style = MaterialTheme.typography.bodyMedium,
            color = MaterialTheme.colorScheme.onSurface,
            maxLines = 1,
            overflow = TextOverflow.Ellipsis,
            modifier = Modifier.padding(top = 6.dp),
        )
        Text(
            text = "最新 第${work.latestChapterNum}话",
            style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
            maxLines = 1,
            overflow = TextOverflow.Ellipsis,
        )
        Row(verticalAlignment = Alignment.CenterVertically) {
            Box(
                modifier = Modifier
                    .size(6.dp)
                    .clip(RoundedCornerShape(3.dp))
                    .background(if (work.autoRefresh) CgStatusOngoing else CgOutline),
            )
            Spacer(Modifier.width(4.dp))
            Text(
                text = formatSourceName(work.source),
                style = MaterialTheme.typography.labelSmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis,
            )
        }
    }
}

/** 列表模式漫画卡片：横向 封面 + 信息 */
@Composable
fun ComicListCard(
    work: Work,
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
) {
    Row(
        modifier = modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(12.dp))
            .background(CgCard)
            .clickable(onClick = onClick)
            .padding(12.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Box(
            modifier = Modifier
                .width(72.dp)
                .aspectRatio(3f / 4f)
                .clip(RoundedCornerShape(8.dp))
                .background(CgSurfaceVariant),
        ) {
            CoverImage(
                r2Path = work.coverR2Path,
                contentDescription = work.title,
                modifier = Modifier.fillMaxSize(),
            )
        }
        Spacer(Modifier.width(12.dp))
        Column(
            modifier = Modifier.weight(1f),
            verticalArrangement = Arrangement.spacedBy(4.dp),
        ) {
            Text(
                text = work.title.ifBlank { "未知标题" },
                style = MaterialTheme.typography.titleMedium,
                color = MaterialTheme.colorScheme.onSurface,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis,
            )
            Text(
                text = "分类：${work.category.ifBlank { "未分类" }}",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                maxLines = 1,
            )
            Text(
                text = "最新 第${work.latestChapterNum}话",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                maxLines = 1,
            )
            Text(
                text = "来源：${formatSourceName(work.source)} · ${if (work.autoRefresh) "自动刷新" else "需PC更新"}",
                style = MaterialTheme.typography.labelSmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                maxLines = 1,
            )
            Text(
                text = formatRelative(work.updateTime.ifBlank { work.createTime }),
                style = MaterialTheme.typography.labelSmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
        StatusBadge(status = work.status)
    }
}


