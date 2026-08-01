using System.Windows;
using Komichi.Desktop.Models;
using Komichi.Desktop.Services;
using Komichi.Desktop.ViewModels;

namespace Komichi.Desktop.Views;

public partial class DetailWindow : Window
{
    private readonly DetailViewModel _vm;

    public DetailWindow(DetailViewModel viewModel)
    {
        InitializeComponent();
        _vm = viewModel;
        DataContext = _vm;

        WindowChromeHelper.Apply(this, cornerRadius: 12);
        WindowChromeHelper.MakeTitleBar(TitleBar);

        _vm.ReadRequested += OpenReader;

        Loaded += async (_, _) => await _vm.LoadAsync();
    }

    private void OpenReader(Chapter chapter)
    {
        var readerVm = new ReaderViewModel(_vm.Api, _vm.WorkId, chapter.ChapterNum);
        var readerWindow = new ReaderWindow(readerVm);
        readerWindow.Owner = this;
        readerWindow.Show();
        _ = readerVm.LoadAsync();
    }

    protected override void OnClosed(EventArgs e)
    {
        _vm.ReadRequested -= OpenReader;
        base.OnClosed(e);
    }
}
