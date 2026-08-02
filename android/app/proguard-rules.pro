# ============================================================
# Komichi Android release 混淆规则
# 启用位置：android/app/build.gradle.kts -> buildTypes.release.isMinifyEnabled = true
# 说明：保留依赖反射所需的类，避免 release 包运行时崩溃。
# ============================================================

# 保留行号，便于崩溃栈定位
-keepattributes SourceFile,LineNumberTable
-renamesourcefileattribute SourceFile

# ---------------- Hilt (Dagger) ----------------
-keep class dagger.hilt.** { *; }
-keep class javax.inject.** { *; }
-keep class * extends dagger.hilt.android.internal.managers.ViewComponentManager$FragmentContextWrapper
-keep class **_HiltModules* { *; }
-keep class **_Hilt_* { *; }
-keep class hilt_aggregated_deps.** { *; }
-keep class dagger.hilt.android.internal.managers.** { *; }

# ---------------- Retrofit / OkHttp / Okio ----------------
-keepattributes Signature, *Annotation*, InnerClasses
-keep class retrofit2.** { *; }
-keep interface retrofit2.** { *; }
-keep class com.squareup.okhttp3.** { *; }
-keep interface com.squareup.okhttp3.** { *; }
-dontwarn retrofit2.**
-dontwarn okhttp3.**
-dontwarn okio.**
-dontwarn com.squareup.okhttp.**

# ---------------- kotlinx.serialization ----------------
-keepattributes *Annotation*, InnerClasses
-dontnote kotlinx.serialization.**
-keep class kotlinx.serialization.** { *; }
-keep class **$$serializer { *; }
-keep class **$Companion { *; }
-keepclasseswithmembers @kotlinx.serialization.Serializable class * { *; }

# ---------------- Coil ----------------
-dontwarn coil.**
-keep class coil.** { *; }

# ---------------- Jetpack Compose / AndroidX ----------------
-keep class androidx.compose.** { *; }
-keep interface androidx.compose.** { *; }
-dontwarn androidx.compose.**
-keep class androidx.datastore.** { *; }
-keep class androidx.lifecycle.** { *; }

# ---------------- 应用数据模型（被序列化/反射使用） ----------------
-keep class com.komichi.**.model.** { *; }
-keep class com.komichi.**.data.** { *; }
-keep class com.komichi.**.domain.** { *; }

# ---------------- Kotlin / Coroutines ----------------
-keep class kotlin.coroutines.** { *; }
-dontwarn kotlinx.coroutines.**
-keepclassmembers class kotlin.Metadata { *; }
