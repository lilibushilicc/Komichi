using System.IO;
using System.Text.Json;

namespace Komichi.Desktop.Services;

/// <summary>
/// 本地配置存储（%AppData%\Komichi\config.json）
/// 保存 Worker 地址、登录 token 和用户信息，实现免登录启动。
/// </summary>
public class AppConfig
{
    private static readonly string ConfigDir =
        Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData), "Komichi");

    private static readonly string ConfigPath = Path.Combine(ConfigDir, "config.json");

    public string WorkerUrl { get; set; } = "https://komichi.270312.xyz";
    public string? Token { get; set; }
    public string? Username { get; set; }
    public string? Role { get; set; }

    /// <summary>载入配置；文件不存在或损坏时返回默认配置。</summary>
    public static AppConfig Load()
    {
        try
        {
            if (File.Exists(ConfigPath))
            {
                var json = File.ReadAllText(ConfigPath);
                return JsonSerializer.Deserialize<AppConfig>(json) ?? new AppConfig();
            }
        }
        catch
        {
            // 配置损坏时静默回退默认值
        }
        return new AppConfig();
    }

    public void Save()
    {
        Directory.CreateDirectory(ConfigDir);
        File.WriteAllText(ConfigPath, JsonSerializer.Serialize(this, new JsonSerializerOptions { WriteIndented = true }));
    }

    public void ClearAuth()
    {
        Token = null;
        Username = null;
        Role = null;
        Save();
    }
}
