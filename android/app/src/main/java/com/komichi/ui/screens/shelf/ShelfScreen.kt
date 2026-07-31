package com.komichi.ui.screens.shelf

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.grid.GridCells
import androidx.compose.foundation.lazy.grid.LazyVerticalGrid
import androidx.compose.foundation.lazy.grid.items as gridItems
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ViewList
import androidx.compose.material.icons.filled.ViewModule
import androidx.compose.material.icons.outlined.CollectionsBookmark
import androidx.compose.material3.FilterChip
import androidx.compose.material3.FilterChipDefaults
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
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
import com.komichi.ui.components.ComicListCard
import com.komichi.ui.components.EmptyState
import com.komichi.ui.components.ErrorState
import com.komichi.ui.components.LoadingState
import com.komichi.viewmodel.ShelfFilter
import com.komichi.viewmodel.ShelfItem
import com.komichi.viewmodel.ShelfViewModel

@Composable
fun ShelfScreen(
    onOpenDetail: (Long) -> Unit,
    viewModel: ShelfViewModel = hiltViewModel(),
) {
    val state by viewModel.uiState.collectAsStateWithLifecycle()
    val viewMode by viewModel.viewMode.collectAsStateWithLifecycle()
    var firstResume by remember { mutableStateOf(true) }
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

    val filtered = filterItems(state.items, state.filter)

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
            horizontalArrangement = Arrangement.SpaceBetween,
        ) {
            Text(
                text = stringResource(R.string.shelf_title),
                style = MaterialTheme.typography.headlineMedium,
                fontWeight = FontWeight.Bold,
                color = MaterialTheme.colorScheme.onBackground,
            )
            IconButton(onClick = viewModel::toggleViewMode) {
                Icon(
                    imageVector = if (viewMode == 0) Icons.AutoMirrored.Filled.ViewList else Icons.Filled.ViewModule,
                    contentDescription = if (viewMode == 0) stringResource(R.string.shelf_view_list) else stringResource(R.string.shelf_view_grid),
                    tint = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
        }

        // 筛选 Chips
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = 16.dp, vertical = 4.dp),
            horizontalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            FilterChipItem(stringResource(R.string.shelf_filter_all), state.filter == ShelfFilter.ALL) {
                viewModel.setFilter(ShelfFilter.ALL)
            }
            FilterChipItem(stringResource(R.string.shelf_filter_updated), state.filter == ShelfFilter.UPDATED) {
                viewModel.setFilter(ShelfFilter.UPDATED)
            }
            FilterChipItem(stringResource(R.string.shelf_filter_reading), state.filter == ShelfFilter.READING) {
                viewModel.setFilter(ShelfFilter.READING)
            }
        }

        when {
            state.isLoading -> LoadingState(label = stringResource(R.string.common_loading))
            state.error != null -> ErrorState(message = state.error!!, onRetry = { viewModel.loadShelf() })
            filtered.isEmpty() -> EmptyState(
                icon = Icons.Outlined.CollectionsBookmark,
                title = "书架空空如也",
                subtitle = stringResource(R.string.shelf_empty),
            )
            viewMode == 0 -> GridShelf(filtered, onOpenDetail)
            else -> ListShelf(filtered, onOpenDetail)
        }
    }
}

@Composable
private fun GridShelf(items: List<ShelfItem>, onOpenDetail: (Long) -> Unit) {
    LazyVerticalGrid(
        columns = GridCells.Fixed(3),
        modifier = Modifier.fillMaxSize(),
        contentPadding = PaddingValues(16.dp),
        horizontalArrangement = Arrangement.spacedBy(12.dp),
        verticalArrangement = Arrangement.spacedBy(16.dp),
    ) {
        gridItems(items, key = { it.work.id }) { item ->
            ComicGridCard(
                work = item.work,
                onClick = { onOpenDetail(item.work.id) },
            )
        }
    }
}

@Composable
private fun ListShelf(items: List<ShelfItem>, onOpenDetail: (Long) -> Unit) {
    LazyColumn(
        modifier = Modifier.fillMaxSize(),
        contentPadding = PaddingValues(16.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        items(items, key = { it.work.id }) { item ->
            Box {
                ComicListCard(work = item.work, onClick = { onOpenDetail(item.work.id) })
                if (item.hasUpdate) {
                    com.komichi.ui.components.StatusBadge(
                        status = com.komichi.data.WorkStatus.ONGOING,
                        modifier = Modifier
                            .align(Alignment.TopEnd)
                            .padding(24.dp),
                    )
                }
            }
        }
    }
}

@Composable
private fun FilterChipItem(label: String, selected: Boolean, onClick: () -> Unit) {
    FilterChip(
        selected = selected,
        onClick = onClick,
        label = { Text(label) },
        shape = RoundedCornerShape(12.dp),
        colors = FilterChipDefaults.filterChipColors(
            selectedContainerColor = MaterialTheme.colorScheme.primaryContainer,
            selectedLabelColor = MaterialTheme.colorScheme.onPrimaryContainer,
            containerColor = MaterialTheme.colorScheme.surface,
            labelColor = MaterialTheme.colorScheme.onSurfaceVariant,
        ),
    )
}

private fun filterItems(items: List<ShelfItem>, filter: ShelfFilter): List<ShelfItem> = when (filter) {
    ShelfFilter.ALL -> items
    ShelfFilter.UPDATED -> items.filter { it.hasUpdate }
    ShelfFilter.READING -> items.filter { it.isReading }
}
