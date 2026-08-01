using System.Windows;
using System.Windows.Input;
using Komichi.Desktop.Services;
using Komichi.Desktop.ViewModels;

namespace Komichi.Desktop.Views;

public partial class LoginWindow : Window
{
    private readonly LoginViewModel _vm;

    public LoginWindow(LoginViewModel viewModel)
    {
        InitializeComponent();
        _vm = viewModel;
        DataContext = _vm;

        WindowChromeHelper.Apply(this, cornerRadius: 14);
        WindowChromeHelper.MakeTitleBar(TitleBar);
    }

    private void PasswordBox_OnPasswordChanged(object sender, RoutedEventArgs e)
    {
        if (DataContext is LoginViewModel vm)
        {
            vm.Password = PasswordBox.Password;
        }
    }

    private void OnKeyDown(object sender, KeyEventArgs e)
    {
        if (e.Key == Key.Enter && _vm.LoginCommand.CanExecute(null))
        {
            _vm.LoginCommand.Execute(null);
        }
    }
}
