using System.Windows.Input;
using Komichi.Desktop.Models;
using Komichi.Desktop.Services;

namespace Komichi.Desktop.ViewModels;

/// <summary>
/// 阅读器 ViewModel：章节导航 + 阅读进度自动同步。
/// 与 Android 端对齐：当前版本为追踪模式（保存阅读进度，不加载漫画图片）。
/// </summary>
public class ReaderViewModel : ObservableObject
{
    private readonly KomichiApiClient _api;
    private readonly long _workId;

    private string _workTitle = "";
    private List<Chapter> _chapters = new();
    private int _currentIndex;
    private string _statusMessage = "";
    private bool _isBusy;
    private bool _isSaving;

    public ReaderViewModel(KomichiApiClient api, long workId, int startChapterNum)
    {
        _api = api;
        _workId = workId;
        _startChapterNum = startChapterNum;

        PrevCommand = new AsyncRelayCommand(() => MoveAsync(-1), () => !_isBusy && CurrentIndex > 0);
        NextCommand = new AsyncRelayCommand(() => MoveAsync(+1), () => !_isBusy && CurrentIndex < _chapters.Count - 1);
    }

    private readonly int _startChapterNum;

    public string WorkTitle
    {
        get => _workTitle;
        private set => SetProperty(ref _workTitle, value);
    }

    public List<Chapter> Chapters
    {
        get => _chapters;
        private set => SetProperty(ref _chapters, value);
    }

    public Chapter? CurrentChapter => Chapters.Count > 0 ? Chapters[CurrentIndex] : null;

    public int CurrentIndex
    {
        get => _currentIndex;
        private set
        {
            if (SetProperty(ref _currentIndex, value))
            {
                OnPropertyChanged(nameof(CurrentChapter));
                OnPropertyChanged(nameof(PositionText));
                CommandManager.InvalidateRequerySuggested();
            }
        }
    }

    public string PositionText =>
        Chapters.Count > 0 ? $"{CurrentIndex + 1} / {Chapters.Count}" : "- / -";

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

    public bool IsSaving
    {
        get => _isSaving;
        private set => SetProperty(ref _isSaving, value);
    }

    public ICommand PrevCommand { get; }
    public ICommand NextCommand { get; }

    public async Task LoadAsync()
    {
        IsBusy = true;
        StatusMessage = "加载中...";
        try
        {
            var result = await _api.GetWorkDetailAsync(_workId);
            if (result.IsSuccess && result.Data != null)
            {
                WorkTitle = result.Data.Title ?? "";
                var chapters = (result.Data.Chapters ?? new List<Chapter>())
                    .OrderBy(c => c.ChapterNum)
                    .ToList();
                Chapters = chapters;

                var index = chapters.FindIndex(c => c.ChapterNum == _startChapterNum);
                CurrentIndex = index >= 0 ? index : 0;
                StatusMessage = "";
                await SaveProgressAsync();
            }
            else
            {
                StatusMessage = result.Msg ?? "加载章节失败";
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

    private async Task MoveAsync(int delta)
    {
        var target = CurrentIndex + delta;
        if (target < 0 || target >= Chapters.Count) return;

        CurrentIndex = target;
        await SaveProgressAsync();
    }

    /// <summary>保存当前章节阅读进度到 Worker（自动同步）</summary>
    public async Task SaveProgressAsync()
    {
        var chapter = CurrentChapter;
        if (chapter == null || _isSaving) return;

        IsSaving = true;
        try
        {
            var result = await _api.SaveBookmarkAsync(_workId, chapter.ChapterNum, note: "reader");
            if (result.IsSuccess)
            {
                StatusMessage = $"已同步进度：第{chapter.ChapterNum}话";
            }
            else
            {
                StatusMessage = $"进度同步失败：{result.Msg}";
            }
        }
        catch (Exception ex)
        {
            StatusMessage = $"进度同步失败：{ex.Message}";
        }
        finally
        {
            IsSaving = false;
        }
    }
}
