using System.Collections.ObjectModel;
using System.IO;
using System.Windows.Input;
using System.Windows.Media.Imaging;
using Komichi.Desktop.Models;
using Komichi.Desktop.Services;

namespace Komichi.Desktop.ViewModels;

/// <summary>书架/记录条目：作品数据 + 异步加载的封面图</summary>
public class WorkItemViewModel : ObservableObject
{
    private BitmapImage? _cover;
    private bool _coverLoading;
    private string? _progressText;

    public WorkItemViewModel(Work work, string? progressText = null, int? readChapterNum = null)
    {
        Work = work;
        _progressText = progressText;
        ReadChapterNum = readChapterNum;
    }

    public Work Work { get; }

    /// <summary>阅读记录条目：上次读到的章节号（用于直达阅读器）</summary>
    public int? ReadChapterNum { get; }

    public long Id => Work.Id;
    public string Title => Work.Title ?? "(未命名)";
    public string Subtitle
    {
        get
        {
            var parts = new List<string>();
            if (!string.IsNullOrEmpty(Work.Source)) parts.Add(Work.Source);
            if (!string.IsNullOrEmpty(Work.Category)) parts.Add(Work.Category);
            if (Work.LatestChapterNum > 0) parts.Add($"更新至第{Work.LatestChapterNum}话");
            return parts.Count > 0 ? string.Join(" · ", parts) : "暂无信息";
        }
    }

    public string StatusBadge
    {
        get
        {
            return Work.Status switch
            {
                "ongoing" => "连载中",
                "completed" => "已完结",
                _ => Work.Status ?? "",
            };
        }
    }

    public string? ProgressText
    {
        get => _progressText;
        set => SetProperty(ref _progressText, value);
    }

    public BitmapImage? Cover
    {
        get => _cover;
        private set => SetProperty(ref _cover, value);
    }

    public bool CoverLoading
    {
        get => _coverLoading;
        private set => SetProperty(ref _coverLoading, value);
    }

    /// <summary>通过 R2 签名 URL 加载封面</summary>
    public async Task LoadCoverAsync(KomichiApiClient api)
    {
        var path = Work.CoverR2Path;
        if (string.IsNullOrWhiteSpace(path) || Cover != null || CoverLoading) return;

        CoverLoading = true;
        try
        {
            var signed = await api.SignR2UrlAsync(path.Trim().TrimStart('/'));
            if (signed.IsSuccess && !string.IsNullOrEmpty(signed.Data?.Url))
            {
                var bytes = await api.DownloadImageAsync(signed.Data!.Url!);
                var bitmap = new BitmapImage();
                bitmap.BeginInit();
                bitmap.CacheOption = BitmapCacheOption.OnLoad;
                bitmap.StreamSource = new MemoryStream(bytes);
                bitmap.EndInit();
                bitmap.Freeze();
                Cover = bitmap;
            }
        }
        catch
        {
            // 封面加载失败时静默，显示占位图
        }
        finally
        {
            CoverLoading = false;
        }
    }
}

/// <summary>主窗口 ViewModel：书架 + 阅读记录 + 导入</summary>
public class MainViewModel : ObservableObject
{
    private readonly AppConfig _config;
    private readonly KomichiApiClient _api;

    private ObservableCollection<WorkItemViewModel> _works = new();
    private ObservableCollection<WorkItemViewModel> _bookmarks = new();
    private string _statusMessage = "";
    private bool _isBusy;
    private string _username = "";
    private string _importUrl = "";
    private bool _showBookmarks;

    public MainViewModel(AppConfig config)
    {
        _config = config;
        _api = new KomichiApiClient(config);
        _username = config.Username ?? "";

        RefreshCommand = new AsyncRelayCommand(LoadAsync);
        LogoutCommand = new RelayCommand(_ => Logout());
        ImportCommand = new AsyncRelayCommand(ImportAsync, () => !IsBusy);
        ToggleViewCommand = new RelayCommand(_ => ToggleView());
    }

    public string Username
    {
        get => _username;
        private set => SetProperty(ref _username, value);
    }

    public AppConfig Config => _config;

    public ObservableCollection<WorkItemViewModel> Works
    {
        get => _works;
        private set => SetProperty(ref _works, value);
    }

    public ObservableCollection<WorkItemViewModel> Bookmarks
    {
        get => _bookmarks;
        private set => SetProperty(ref _bookmarks, value);
    }

    public string StatusMessage
    {
        get => _statusMessage;
        set => SetProperty(ref _statusMessage, value);
    }

    public bool IsBusy
    {
        get => _isBusy;
        set
        {
            if (SetProperty(ref _isBusy, value))
            {
                CommandManager.InvalidateRequerySuggested();
            }
        }
    }

    public string ImportUrl
    {
        get => _importUrl;
        set => SetProperty(ref _importUrl, value);
    }

    public bool ShowBookmarks
    {
        get => _showBookmarks;
        set
        {
            if (SetProperty(ref _showBookmarks, value))
            {
                OnPropertyChanged(nameof(WorksVisibility));
                OnPropertyChanged(nameof(BookmarksVisibility));
            }
        }
    }

    public System.Windows.Visibility WorksVisibility =>
        ShowBookmarks ? System.Windows.Visibility.Collapsed : System.Windows.Visibility.Visible;

    public System.Windows.Visibility BookmarksVisibility =>
        ShowBookmarks ? System.Windows.Visibility.Visible : System.Windows.Visibility.Collapsed;

    public string ViewToggleText => ShowBookmarks ? "查看书架" : "查看阅读记录";

    public ICommand RefreshCommand { get; }
    public ICommand LogoutCommand { get; }
    public ICommand ImportCommand { get; }
    public ICommand ToggleViewCommand { get; }

    public event Action? LoggedOut;

    public async Task LoadAsync()
    {
        IsBusy = true;
        StatusMessage = "加载中...";
        try
        {
            var worksTask = _api.GetWorkListAsync(page: 1, size: 100);
            var bookmarksTask = _api.GetBookmarkListAsync();
            await Task.WhenAll(worksTask, bookmarksTask);

            var worksResult = await worksTask;
            if (worksResult.IsSuccess)
            {
                var items = (worksResult.Data?.List ?? new List<Work>())
                    .OrderByDescending(w => w.CreateTime)
                    .Select(w => new WorkItemViewModel(w))
                    .ToList();
                Works = new ObservableCollection<WorkItemViewModel>(items);
                _ = LoadCoversAsync(Works);
                StatusMessage = $"共 {Works.Count} 部作品";
            }
            else
            {
                StatusMessage = worksResult.Msg ?? "加载作品失败";
            }

            var bmResult = await bookmarksTask;
            if (bmResult.IsSuccess)
            {
                var items = (bmResult.Data?.List ?? new List<BookmarkItem>())
                    .Select(b =>
                    {
                        var work = new Work
                        {
                            Id = b.WorkId,
                            Title = b.Title,
                            CoverR2Path = b.CoverR2Path,
                            Source = b.Status,
                            Category = b.Category,
                            Status = b.Status,
                            LatestChapterNum = b.LatestChapterNum ?? 0,
                        };
                        var progress = b.ChapterNum > 0
                            ? $"读到第{b.ChapterNum}话"
                            : "尚未开始";
                        if (b.LatestChapterNum > 0)
                        {
                            progress += $" / 共{b.LatestChapterNum}话";
                        }
                        return new WorkItemViewModel(work, progress, b.ChapterNum > 0 ? b.ChapterNum : null);
                    })
                    .ToList();
                Bookmarks = new ObservableCollection<WorkItemViewModel>(items);
                _ = LoadCoversAsync(Bookmarks);
            }
        }
        catch (Exception ex)
        {
            StatusMessage = $"加载失败：{ex.Message}";
        }
        finally
        {
            IsBusy = false;
        }
    }

    private async Task LoadCoversAsync(ObservableCollection<WorkItemViewModel> items)
    {
        foreach (var item in items)
        {
            await item.LoadCoverAsync(_api);
        }
    }

    private async Task ImportAsync()
    {
        var url = ImportUrl.Trim();
        if (string.IsNullOrEmpty(url))
        {
            StatusMessage = "请输入源站 URL（如 https://www.mh160mh.com/kanmanhua/94/）";
            return;
        }

        IsBusy = true;
        StatusMessage = "正在导入，Worker 爬取可能需要几十秒...";
        try
        {
            var result = await _api.ImportWorkAsync(url);
            if (result.IsSuccess && result.Data != null)
            {
                StatusMessage = $"导入成功：《{result.Data.Title}》（{result.Data.ChapterCount} 话，新增 {result.Data.NewChapters} 话）";
                await LoadAsync();
            }
            else
            {
                StatusMessage = result.Msg ?? "导入失败";
            }
        }
        catch (Exception ex)
        {
            StatusMessage = $"导入失败：{ex.Message}";
        }
        finally
        {
            IsBusy = false;
        }
    }

    private void ToggleView()
    {
        ShowBookmarks = !ShowBookmarks;
        OnPropertyChanged(nameof(ViewToggleText));
    }

    private void Logout()
    {
        _config.ClearAuth();
        LoggedOut?.Invoke();
    }
}
