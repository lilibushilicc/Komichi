@file:OptIn(androidx.compose.material3.ExperimentalMaterial3Api::class)

package com.komichi.ui.screens.reader

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.TopAppBarDefaults
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.komichi.R
import com.komichi.ui.components.ErrorState
import com.komichi.ui.components.LoadingState
import com.komichi.viewmodel.ReaderViewModel

@Composable
fun ReaderScreen(
    onBack: () -> Unit,
    viewModel: ReaderViewModel = hiltViewModel(),
) {
    val state by viewModel.uiState.collectAsStateWithLifecycle()

    Scaffold(
        containerColor = MaterialTheme.colorScheme.background,
        topBar = {
            TopAppBar(
                title = {
                    Column {
                        Text(
                            text = state.workTitle,
                            style = MaterialTheme.typography.titleMedium,
                            maxLines = 1,
                            overflow = TextOverflow.Ellipsis,
                        )
                        val chapter = state.currentChapter
                        if (chapter != null) {
                            Text(
                                text = "第${chapter.chapterNum}话" + chapter.chapterTitle.takeIf { it.isNotBlank() }?.let { " · $it" } ?: "",
                                style = MaterialTheme.typography.labelSmall,
                                color = MaterialTheme.colorScheme.onSurfaceVariant,
                            )
                        }
                    }
                },
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = "返回")
                    }
                },
                colors = TopAppBarDefaults.topAppBarColors(
                    containerColor = MaterialTheme.colorScheme.background,
                    titleContentColor = MaterialTheme.colorScheme.onBackground,
                    navigationIconContentColor = MaterialTheme.colorScheme.onBackground,
                ),
            )
        },
        bottomBar = {
            Surface(tonalElevation = 2.dp) {
                Row(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(horizontal = 16.dp, vertical = 10.dp),
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    OutlinedButton(
                        onClick = { viewModel.openChapter(state.currentIndex - 1) },
                        enabled = state.currentIndex > 0,
                    ) {
                        Text(stringResource(R.string.reader_prev))
                    }
                    Spacer(Modifier.weight(1f))
                    if (state.chapters.isNotEmpty()) {
                        Text(
                            text = "${state.currentIndex + 1} / ${state.chapters.size}",
                            style = MaterialTheme.typography.labelMedium,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                    }
                    Spacer(Modifier.weight(1f))
                    OutlinedButton(
                        onClick = { viewModel.openChapter(state.currentIndex + 1) },
                        enabled = state.currentIndex < state.chapters.size - 1,
                    ) {
                        Text(stringResource(R.string.reader_next))
                    }
                }
            }
        },
    ) { padding ->
        when {
            state.isLoading -> LoadingState(modifier = Modifier.padding(padding))
            state.error != null -> ErrorState(
                message = state.error!!,
                onRetry = viewModel::retry,
                modifier = Modifier.padding(padding),
            )
            else -> Column(
                modifier = Modifier
                    .fillMaxSize()
                    .padding(padding)
                    .padding(horizontal = 32.dp, vertical = 48.dp),
                horizontalAlignment = Alignment.CenterHorizontally,
                verticalArrangement = Arrangement.Center,
            ) {
                val chapter = state.currentChapter
                if (chapter != null) {
                    Text(
                        text = "第${chapter.chapterNum}话",
                        style = MaterialTheme.typography.headlineSmall,
                        color = MaterialTheme.colorScheme.onBackground,
                    )
                    if (chapter.chapterTitle.isNotBlank()) {
                        Spacer(Modifier.width(8.dp))
                        Text(
                            text = chapter.chapterTitle,
                            style = MaterialTheme.typography.bodyLarge,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                            maxLines = 3,
                            overflow = TextOverflow.Ellipsis,
                        )
                    }
                    Spacer(Modifier.width(24.dp))
                }
                Text(
                    text = stringResource(R.string.reader_tracking_only),
                    style = MaterialTheme.typography.bodyMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
        }
    }
}
