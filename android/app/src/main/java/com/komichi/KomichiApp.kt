package com.komichi

import android.app.Application
import coil.ImageLoader
import coil.ImageLoaderFactory
import com.komichi.di.AppEntryPoint
import com.komichi.util.R2SignInterceptor
import dagger.hilt.android.EntryPointAccessors
import dagger.hilt.android.HiltAndroidApp

@HiltAndroidApp
class KomichiApp : Application(), ImageLoaderFactory {

    override fun newImageLoader(): ImageLoader {
        val entryPoint = EntryPointAccessors.fromApplication(
            this, AppEntryPoint::class.java
        )
        return ImageLoader.Builder(this)
            .components {
                add(R2SignInterceptor(entryPoint.apiService()))
            }
            .build()
    }
}