using System.Windows.Input;
using Komichi.Desktop.Models;
using Komichi.Desktop.Services;

namespace Komichi.Desktop.ViewModels;

/// <summary>作品详情页 ViewModel：详情 + 章节列表 + 检查更新</summary>
public class DetailViewModel : ObservableObject
{
    private readonly KomichiApiClient _api;
    private readonly long _workId;

    private Work? _work;
    private Chapter? _selectedChapter;
    private string _statusMessage = "";
    private bool _isBusy;
    private bool _checkingUpdate;

    public DetailViewModel(KomichiApiClient api, long workId)
    {
        _api = api;
        _workId = workId;
        LoadCommand = new AsyncRelayCommand(LoadAsync);
        CheckUpdateCommand = new AsyncRelayCommand(CheckUpdateAsync, () => !_checkingUpdate);
        ReadSelectedCommand = new RelayCommand(_ => ReadSelected(), _ => SelectedChapter != null);
    }

    public KomichiApiClient Api => _api;

    public long WorkId => _workId;

    public Work? Work
    {
        get => _work;
        private set => SetProperty(ref _work, value);
    }

    public Chapter? SelectedChapter
    {
        get => _selectedChapter;
        set
        {
            if (SetProperty(ref _selectedChapter, value))
            {
                CommandManager.InvalidateRequerySuggested();
            }
        }
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

    public string ChapterCountText =>
        Work?.Chapters is { Count: > 0 } chapters ? $"共 {chapters.Count} 话" : "暂无章节";

    public ICommand LoadCommand { get; }
    public ICommand CheckUpdateCommand { get; }
    public ICommand ReadSelectedCommand { get; }

    /// <summary>进入阅读器（由窗口处理导航）</summary>
    public event Action<Chapter>? ReadRequested;

    public async Task LoadAsync()
    {
        IsBusy = true;
        StatusMessage = "加载中...";
        try
        {
            var result = await _api.GetWorkDetailAsync(_workId);
            if (result.IsSuccess)
            {
                Work = result.Data;
                StatusMessage = "";
            }
            else
            {
                StatusMessage = result.Msg ?? "加载作品详情失败";
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

    public async Task CheckUpdateAsync()
    {
        if (_checkingUpdate) return;
        _checkingUpdate = true;
        CommandManager.InvalidateRequerySuggested();
        StatusMessage = "正在检查源站更新...";
        try
        {
            var result = await _api.CheckUpdateAsync(_workId, force: true);
            if (result.IsSuccess && result.Data != null)
            {
                if (result.Data.HasUpdate)
                {
                    StatusMessage = $"发现 {result.Data.NewChapterCount} 个新章节！";
                }
                else
                {
                    StatusMessage = result.Data.ForceError != null
                        ? $"检查完成（源站爬取出错：{result.Data.ForceError}）"
                        : "已是最新，没有新章节";
                }
                await LoadAsync();
            }
            else
            {
                StatusMessage = result.Msg ?? "检查更新失败";
            }
        }
        catch (Exception ex)
        {
            StatusMessage = $"检查更新失败：{ex.Message}";
        }
        finally
        {
            _checkingUpdate = false;
            CommandManager.InvalidateRequerySuggested();
        }
    }

    private void ReadSelected()
    {
        if (SelectedChapter != null)
        {
            ReadRequested?.Invoke(SelectedChapter);
        }
    }

    /// <summary>从书架继续阅读：定位到指定章节</summary>
    public void SelectChapter(int chapterNum)
    {
        if (Work?.Chapters == null) return;
        var chapter = Work.Chapters.FirstOrDefault(c => c.ChapterNum == chapterNum)
            ?? Work.Chapters.OrderBy(c => c.ChapterNum).FirstOrDefault();
        if (chapter != null)
        {
            SelectedChapter = chapter;
        }
    }
}
