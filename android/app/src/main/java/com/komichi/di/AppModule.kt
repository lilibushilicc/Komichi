package com.komichi.di

import com.komichi.api.ApiClient
import com.komichi.api.ApiService
import dagger.Module
import dagger.Provides
import dagger.hilt.EntryPoint
import dagger.hilt.InstallIn
import dagger.hilt.components.SingletonComponent
import javax.inject.Singleton

@Module
@InstallIn(SingletonComponent::class)
object AppModule {

    @Provides
    @Singleton
    fun provideApiService(apiClient: ApiClient): ApiService = apiClient.apiService
}

/**
 * 供 Application 在构建全局 Coil ImageLoader 时获取 ApiService。
 */
@EntryPoint
@InstallIn(SingletonComponent::class)
interface AppEntryPoint {
    fun apiService(): ApiService
}
