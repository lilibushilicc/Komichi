using System.Text.Json.Serialization;

namespace Komichi.Desktop.Models;

/// <summary>Worker 统一响应结构 { code, msg, data }</summary>
public class ApiResponse<T>
{
    [JsonPropertyName("code")] public int Code { get; set; }
    [JsonPropertyName("msg")] public string? Msg { get; set; }
    [JsonPropertyName("data")] public T? Data { get; set; }

    public bool IsSuccess => Code >= 200 && Code < 300;
}

public class UserInfo
{
    [JsonPropertyName("id")] public long Id { get; set; }
    [JsonPropertyName("username")] public string? Username { get; set; }
    [JsonPropertyName("role")] public string? Role { get; set; }
}

public class LoginData
{
    [JsonPropertyName("token")] public string? Token { get; set; }
    [JsonPropertyName("user")] public UserInfo? User { get; set; }
}

/// <summary>作品（/api/work/list、/api/work/:id 共用字段）</summary>
public class Work
{
    [JsonPropertyName("id")] public long Id { get; set; }
    [JsonPropertyName("title")] public string? Title { get; set; }
    [JsonPropertyName("category")] public string? Category { get; set; }
    [JsonPropertyName("description")] public string? Description { get; set; }
    [JsonPropertyName("cover_r2_path")] public string? CoverR2Path { get; set; }
    [JsonPropertyName("source")] public string? Source { get; set; }
    [JsonPropertyName("source_url")] public string? SourceUrl { get; set; }
    [JsonPropertyName("latest_chapter_num")] public int LatestChapterNum { get; set; }
    [JsonPropertyName("status")] public string? Status { get; set; }
    [JsonPropertyName("create_time")] public string? CreateTime { get; set; }
    [JsonPropertyName("auto_refresh")] public bool AutoRefresh { get; set; }
    [JsonPropertyName("chapters")] public List<Chapter>? Chapters { get; set; }
}

public class Chapter
{
    [JsonPropertyName("id")] public long Id { get; set; }
    [JsonPropertyName("work_id")] public long WorkId { get; set; }
    [JsonPropertyName("chapter_num")] public int ChapterNum { get; set; }
    [JsonPropertyName("chapter_title")] public string? ChapterTitle { get; set; }
    [JsonPropertyName("create_time")] public string? CreateTime { get; set; }

    public string DisplayName
    {
        get
        {
            var title = string.IsNullOrWhiteSpace(ChapterTitle) ? "" : ChapterTitle.Trim();
            return $"第{ChapterNum}话" + (title.Length > 0 ? " · " + title : "");
        }
    }
}

public class WorkListData
{
    [JsonPropertyName("list")] public List<Work>? List { get; set; }
    [JsonPropertyName("total")] public long Total { get; set; }
    [JsonPropertyName("page")] public int Page { get; set; }
    [JsonPropertyName("size")] public int Size { get; set; }
}

/// <summary>阅读记录（/api/bookmark/list）</summary>
public class BookmarkItem
{
    [JsonPropertyName("id")] public long Id { get; set; }
    [JsonPropertyName("user_id")] public long UserId { get; set; }
    [JsonPropertyName("work_id")] public long WorkId { get; set; }
    [JsonPropertyName("chapter_num")] public int ChapterNum { get; set; }
    [JsonPropertyName("note")] public string? Note { get; set; }
    [JsonPropertyName("last_read_time")] public string? LastReadTime { get; set; }
    [JsonPropertyName("title")] public string? Title { get; set; }
    [JsonPropertyName("cover_r2_path")] public string? CoverR2Path { get; set; }
    [JsonPropertyName("status")] public string? Status { get; set; }
    [JsonPropertyName("latest_chapter_num")] public int? LatestChapterNum { get; set; }
    [JsonPropertyName("category")] public string? Category { get; set; }
}

public class BookmarkListData
{
    [JsonPropertyName("list")] public List<BookmarkItem>? List { get; set; }
}

public class SignUrlData
{
    [JsonPropertyName("url")] public string? Url { get; set; }
    [JsonPropertyName("path")] public string? Path { get; set; }
    [JsonPropertyName("expire")] public long Expire { get; set; }
}

public class CheckUpdateData
{
    [JsonPropertyName("work")] public Work? Work { get; set; }
    [JsonPropertyName("latest_chapter")] public Chapter? LatestChapter { get; set; }
    [JsonPropertyName("has_update")] public bool HasUpdate { get; set; }
    [JsonPropertyName("new_chapter_count")] public int NewChapterCount { get; set; }
    [JsonPropertyName("force_error")] public string? ForceError { get; set; }
}

public class SaveBookmarkData
{
    [JsonPropertyName("bookmark_id")] public long BookmarkId { get; set; }
}

public class ImportData
{
    [JsonPropertyName("work_id")] public long WorkId { get; set; }
    [JsonPropertyName("title")] public string? Title { get; set; }
    [JsonPropertyName("source")] public string? Source { get; set; }
    [JsonPropertyName("chapter_count")] public int ChapterCount { get; set; }
    [JsonPropertyName("new_chapters")] public int NewChapters { get; set; }
}
