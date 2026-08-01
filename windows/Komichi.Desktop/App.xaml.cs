using System.Windows;
using System.Windows.Threading;
using Komichi.Desktop.Services;
using Komichi.Desktop.ViewModels;
using Komichi.Desktop.Views;

namespace Komichi.Desktop;

/// <summary>
/// 应用入口：根据本地配置决定是否直接进入主界面（免登录）。
/// </summary>
public partial class App : Application
{
    private AppConfig? _config;

    protected override void OnStartup(StartupEventArgs e)
    {
        base.OnStartup(e);

        // 全局异常兜底（线程与 UI 异常）
        DispatcherUnhandledException += (_, args) =>
        {
            MessageBox.Show(
                $"发生未处理的错误：\n{args.Exception.Message}",
                "Komichi",
                MessageBoxButton.OK,
                MessageBoxImage.Error);
            args.Handled = true;
        };

        _config = AppConfig.Load();

        if (!string.IsNullOrEmpty(_config.Token) && !string.IsNullOrEmpty(_config.WorkerUrl))
        {
            OpenMainWindow();
        }
        else
        {
            OpenLoginWindow();
        }
    }

    public void OpenLoginWindow()
    {
        MainWindow?.Close();
        var vm = new LoginViewModel(_config!);
        var window = new LoginWindow(vm);
        vm.LoginCompleted += success =>
        {
            if (success)
            {
                OpenMainWindow();
            }
        };
        window.Show();
    }

    public void OpenMainWindow()
    {
        MainWindow?.Close();
        var vm = new MainViewModel(_config!);
        var window = new MainWindow(vm);
        vm.LoggedOut += () =>
        {
            window.Close();
            OpenLoginWindow();
        };
        MainWindow = window;
        window.Show();
        window.Activate();

        // 启动后异步加载书架
        _ = vm.LoadAsync();
    }
}
