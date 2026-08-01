using System.Windows;
using System.Windows.Input;
using Komichi.Desktop.Services;
using Komichi.Desktop.ViewModels;

namespace Komichi.Desktop.Views;

public partial class ReaderWindow : Window
{
    private readonly ReaderViewModel _vm;

    public ReaderWindow(ReaderViewModel viewModel)
    {
        InitializeComponent();
        _vm = viewModel;
        DataContext = _vm;

        WindowChromeHelper.Apply(this, cornerRadius: 12);
        WindowChromeHelper.MakeTitleBar(TitleBar);
    }

    private void OnKeyDown(object sender, KeyEventArgs e)
    {
        switch (e.Key)
        {
            case Key.Left:
            case Key.PageUp:
                if (_vm.PrevCommand.CanExecute(null))
                {
                    _vm.PrevCommand.Execute(null);
                    e.Handled = true;
                }
                break;
            case Key.Right:
            case Key.PageDown:
                if (_vm.NextCommand.CanExecute(null))
                {
                    _vm.NextCommand.Execute(null);
                    e.Handled = true;
                }
                break;
        }
    }
}
