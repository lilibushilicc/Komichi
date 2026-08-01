using System.Windows.Input;
using Komichi.Desktop.Services;

namespace Komichi.Desktop.ViewModels;

/// <summary>登录页 ViewModel</summary>
public class LoginViewModel : ObservableObject
{
    private readonly AppConfig _config;
    private readonly KomichiApiClient _api;

    private string _workerUrl = "";
    private string _username = "";
    private string _password = "";
    private string _statusMessage = "";
    private bool _isBusy;

    public LoginViewModel(AppConfig config)
    {
        _config = config;
        _api = new KomichiApiClient(config);
        _workerUrl = config.WorkerUrl;
        _username = config.Username ?? "";
        LoginCommand = new AsyncRelayCommand(LoginAsync, () => !IsBusy);
    }

    public string WorkerUrl
    {
        get => _workerUrl;
        set => SetProperty(ref _workerUrl, value);
    }

    public string Username
    {
        get => _username;
        set => SetProperty(ref _username, value);
    }

    public string Password
    {
        get => _password;
        set => SetProperty(ref _password, value);
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

    public bool IsError { get; private set; }

    public ICommand LoginCommand { get; }

    public bool IsAuthenticated => !string.IsNullOrEmpty(_config.Token);

    public event Action<bool>? LoginCompleted;

    private async Task LoginAsync()
    {
        var url = WorkerUrl.Trim().TrimEnd('/');
        if (string.IsNullOrEmpty(url) || !url.StartsWith("http"))
        {
            StatusMessage = "请输入有效的 Worker 地址（以 http:// 或 https:// 开头）";
            IsError = true;
            return;
        }
        if (string.IsNullOrEmpty(Username) || string.IsNullOrEmpty(Password))
        {
            StatusMessage = "请输入用户名和密码";
            IsError = true;
            return;
        }

        _config.WorkerUrl = url;
        IsBusy = true;
        StatusMessage = "";
        try
        {
            var result = await _api.LoginAsync(Username.Trim(), Password);
            if (result.IsSuccess)
            {
                StatusMessage = $"登录成功，欢迎 {result.Data!.User?.Username ?? Username}！";
                IsError = false;
                LoginCompleted?.Invoke(true);
            }
            else
            {
                StatusMessage = result.Msg ?? "登录失败";
                IsError = true;
                LoginCompleted?.Invoke(false);
            }
        }
        catch (Exception ex)
        {
            StatusMessage = $"无法连接服务器：{ex.Message}";
            IsError = true;
            LoginCompleted?.Invoke(false);
        }
        finally
        {
            IsBusy = false;
        }
    }
}
