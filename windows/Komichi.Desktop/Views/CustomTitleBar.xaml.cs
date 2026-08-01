using System.Windows;
using System.Windows.Controls;
using Komichi.Desktop.Services;

namespace Komichi.Desktop.Views;

public partial class CustomTitleBar : UserControl
{
    public CustomTitleBar()
    {
        InitializeComponent();
        Loaded += (_, _) =>
        {
            var window = Window.GetWindow(this);
            if (window != null)
            {
                window.StateChanged += (_, _) => UpdateMaxIcon(window);
                UpdateMaxIcon(window);
            }
        };
    }

    private void UpdateMaxIcon(Window window)
    {
        // 图标简单切换：最大化时显示还原样式（两条横线）
        MaxBtn.ToolTip = window.WindowState == WindowState.Maximized ? "还原" : "最大化";
    }

    private void Minimize_OnClick(object sender, RoutedEventArgs e)
    {
        if (Window.GetWindow(this) is { } w) w.WindowState = WindowState.Minimized;
    }

    private void Maximize_OnClick(object sender, RoutedEventArgs e)
    {
        if (Window.GetWindow(this) is not { } w) return;
        w.WindowState = w.WindowState == WindowState.Maximized
            ? WindowState.Normal
            : WindowState.Maximized;
    }

    private void Close_OnClick(object sender, RoutedEventArgs e)
    {
        if (Window.GetWindow(this) is { } w) w.Close();
    }
}
