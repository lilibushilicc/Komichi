package com.komichi.api

import com.komichi.data.LoginRequest
import com.komichi.data.SaveBookmarkRequest
import com.komichi.data.WorkDetail
import retrofit2.http.Body
import retrofit2.http.GET
import retrofit2.http.POST
import retrofit2.http.Path
import retrofit2.http.Query

interface ApiService {

    /** 健康检查 */
    @GET("/ping")
    suspend fun ping(): ApiResponse<Map<String, String>>

    /** 登录 */
    @POST("/api/auth/login")
    suspend fun login(@Body body: LoginRequest): ApiResponse<LoginResponse>

    /** 作品列表 */
    @GET("/api/work/list")
    suspend fun getWorkList(
        @Query("page") page: Int = 1,
        @Query("size") size: Int = 100,
        @Query("status") status: String? = null,
    ): ApiResponse<WorkListResponse>

    /** 作品详情 + 章节列表 */
    @GET("/api/work/{id}")
    suspend fun getWorkDetail(@Path("id") id: Long): ApiResponse<WorkDetail>

    /** 书签列表 */
    @GET("/api/bookmark/list")
    suspend fun getBookmarkList(): ApiResponse<BookmarkListResponse>

    /** 保存阅读进度 */
    @POST("/api/bookmark/save")
    suspend fun saveBookmark(@Body body: SaveBookmarkRequest): ApiResponse<SaveBookmarkResponse>

    /** 删除书签 */
    @POST("/api/bookmark/delete")
    suspend fun deleteBookmark(@Body body: Map<String, Long>): ApiResponse<Unit>

    /** 获取 R2 图片签名 URL */
    @GET("/api/r2/sign")
    suspend fun signR2Url(@Query("path") path: String): ApiResponse<SignUrlResponse>

    /** 检查作品更新 */
    @GET("/api/work/check/{id}")
    suspend fun checkUpdate(@Path("id") id: Long): ApiResponse<CheckUpdateResponse>

    /** 删除作品 */
    @POST("/api/work/delete")
    suspend fun deleteWork(@Body body: Map<String, Long>): ApiResponse<Unit>
}
