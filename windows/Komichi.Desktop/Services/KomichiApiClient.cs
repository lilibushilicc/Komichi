using System.Net.Http;
using System.Net.Http.Headers;
using System.Text;
using System.Text.Json;
using Komichi.Desktop.Models;

namespace Komichi.Desktop.Services;

/// <summary>
/// Komichi Worker API 客户端。
/// 封装登录、作品列表/详情、阅读进度、R2 图片签名等端点。
/// </summary>
public class KomichiApiClient
{
    private readonly HttpClient _http = new() { Timeout = TimeSpan.FromSeconds(60) };
    private readonly AppConfig _config;

    public KomichiApiClient(AppConfig config)
    {
        _config = config;
        _http.DefaultRequestHeaders.UserAgent.ParseAdd("Komichi.Desktop/1.0");
    }

    public AppConfig Config => _config;

    /// <summary>Worker 基地址，末尾不带斜杠</summary>
    public string BaseUrl => _config.WorkerUrl.TrimEnd('/');

    private HttpRequestMessage BuildRequest(HttpMethod method, string path)
    {
        var request = new HttpRequestMessage(method, $"{BaseUrl}{path}");
        if (!string.IsNullOrEmpty(_config.Token))
        {
            request.Headers.Authorization = new AuthenticationHeaderValue("Bearer", _config.Token);
        }
        return request;
    }

    private static async Task<ApiResponse<T>> ParseResponseAsync<T>(HttpResponseMessage resp, string context)
    {
        var body = await resp.Content.ReadAsStringAsync();
        try
        {
            var parsed = JsonSerializer.Deserialize<ApiResponse<T>>(body);
            if (parsed != null) return parsed;
        }
        catch (JsonException)
        {
            // 非 JSON 响应（如 502 网关错误页），构造错误信息
        }

        var msg = string.IsNullOrWhiteSpace(body)
            ? $"服务返回空响应 (HTTP {(int)resp.StatusCode})"
            : $"服务返回异常格式 (HTTP {(int)resp.StatusCode})";
        return new ApiResponse<T> { Code = (int)resp.StatusCode, Msg = $"{context}失败：{msg}" };
    }

    private static StringContent JsonBody(object obj) =>
        new(JsonSerializer.Serialize(obj), Encoding.UTF8, "application/json");

    /// <summary>登录，成功后把 token 写入配置并保存。</summary>
    public async Task<ApiResponse<LoginData>> LoginAsync(string username, string password)
    {
        using var request = BuildRequest(HttpMethod.Post, "/api/auth/login");
        request.Content = JsonBody(new { username, password });

        using var resp = await _http.SendAsync(request);
        var result = await ParseResponseAsync<LoginData>(resp, "登录");
        if (result.IsSuccess && result.Data?.Token != null)
        {
            _config.Token = result.Data.Token;
            _config.Username = result.Data.User?.Username ?? username;
            _config.Role = result.Data.User?.Role;
            _config.Save();
        }
        return result;
    }

    /// <summary>获取作品列表（分页）</summary>
    public async Task<ApiResponse<WorkListData>> GetWorkListAsync(int page = 1, int size = 100, string? status = null)
    {
        var query = new StringBuilder($"/api/work/list?page={page}&size={size}");
        if (!string.IsNullOrEmpty(status)) query.Append($"&status={Uri.EscapeDataString(status)}");

        using var request = BuildRequest(HttpMethod.Get, query.ToString());
        using var resp = await _http.SendAsync(request);
        return await ParseResponseAsync<WorkListData>(resp, "获取作品列表");
    }

    /// <summary>获取作品详情（含章节列表）</summary>
    public async Task<ApiResponse<Work>> GetWorkDetailAsync(long id)
    {
        using var request = BuildRequest(HttpMethod.Get, $"/api/work/{id}");
        using var resp = await _http.SendAsync(request);
        return await ParseResponseAsync<Work>(resp, "获取作品详情");
    }

    /// <summary>获取阅读记录列表</summary>
    public async Task<ApiResponse<BookmarkListData>> GetBookmarkListAsync()
    {
        using var request = BuildRequest(HttpMethod.Get, "/api/bookmark/list");
        using var resp = await _http.SendAsync(request);
        return await ParseResponseAsync<BookmarkListData>(resp, "获取阅读记录");
    }

    /// <summary>保存/更新阅读进度</summary>
    public async Task<ApiResponse<SaveBookmarkData>> SaveBookmarkAsync(long workId, int chapterNum, string? note = null)
    {
        using var request = BuildRequest(HttpMethod.Post, "/api/bookmark/save");
        request.Content = JsonBody(new { work_id = workId, chapter_num = chapterNum, note });

        using var resp = await _http.SendAsync(request);
        return await ParseResponseAsync<SaveBookmarkData>(resp, "保存阅读进度");
    }

    /// <summary>删除阅读记录</summary>
    public async Task<ApiResponse<object>> DeleteBookmarkAsync(long workId)
    {
        using var request = BuildRequest(HttpMethod.Post, "/api/bookmark/delete");
        request.Content = JsonBody(new { work_id = workId });

        using var resp = await _http.SendAsync(request);
        return await ParseResponseAsync<object>(resp, "删除阅读记录");
    }

    /// <summary>获取 R2 图片签名 URL（用于显示封面）</summary>
    public async Task<ApiResponse<SignUrlData>> SignR2UrlAsync(string path)
    {
        using var request = BuildRequest(HttpMethod.Get, $"/api/r2/sign?path={Uri.EscapeDataString(path)}");
        using var resp = await _http.SendAsync(request);
        return await ParseResponseAsync<SignUrlData>(resp, "获取图片地址");
    }

    /// <summary>检查作品更新（force=true 时实时爬取源站）</summary>
    public async Task<ApiResponse<CheckUpdateData>> CheckUpdateAsync(long id, bool force = false)
    {
        using var request = BuildRequest(HttpMethod.Get, $"/api/work/check/{id}?force={force}");
        using var resp = await _http.SendAsync(request);
        return await ParseResponseAsync<CheckUpdateData>(resp, "检查更新");
    }

    /// <summary>通过 source_url 导入作品（USER/CRAWLER 均可）</summary>
    public async Task<ApiResponse<ImportData>> ImportWorkAsync(string sourceUrl)
    {
        using var request = BuildRequest(HttpMethod.Post, "/api/work/import");
        request.Content = JsonBody(new { source_url = sourceUrl });

        using var resp = await _http.SendAsync(request);
        return await ParseResponseAsync<ImportData>(resp, "导入作品");
    }

    /// <summary>下载图片字节（带签名 URL 或绝对 URL 均可）</summary>
    public async Task<byte[]> DownloadImageAsync(string url)
    {
        using var request = new HttpRequestMessage(HttpMethod.Get, url);
        using var resp = await _http.SendAsync(request);
        resp.EnsureSuccessStatusCode();
        return await resp.Content.ReadAsByteArrayAsync();
    }
}
