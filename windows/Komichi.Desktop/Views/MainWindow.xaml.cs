using System.Windows;
using System.Windows.Input;
using Komichi.Desktop.Services;
using Komichi.Desktop.ViewModels;

namespace Komichi.Desktop.Views;

public partial class MainWindow : Window
{
    private readonly MainViewModel _vm;

    public MainWindow(MainViewModel viewModel)
    {
        InitializeComponent();
        _vm = viewModel;
        DataContext = _vm;

        WindowChromeHelper.Apply(this, cornerRadius: 12);
        WindowChromeHelper.MakeTitleBar(TitleBar);
    }

    private void WorkCard_OnMouseLeftButtonUp(object sender, MouseButtonEventArgs e)
    {
        if (sender is FrameworkElement { DataContext: WorkItemViewModel item })
        {
            var api = new KomichiApiClient(_vm.Config);

            // 阅读记录条目：直达阅读器（从上次章节继续）
            if (item.ReadChapterNum is int chapterNum)
            {
                var readerVm = new ReaderViewModel(api, item.Id, chapterNum);
                var readerWindow = new ReaderWindow(readerVm);
                readerWindow.Owner = this;
                readerWindow.Show();
                _ = readerVm.LoadAsync();
                return;
            }

            // 书架条目：打开作品详情
            var detailVm = new DetailViewModel(api, item.Id);
            var detailWindow = new DetailWindow(detailVm);
            detailWindow.Owner = this;
            detailWindow.Show();
        }
    }
}
