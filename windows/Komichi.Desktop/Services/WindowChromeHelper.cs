using System.Runtime.InteropServices;
using System.Windows;
using System.Windows.Input;
using System.Windows.Interop;
using System.Windows.Media;

namespace Komichi.Desktop.Services;

/// <summary>
/// 自定义窗口样式助手：
/// - 去掉系统标题栏，窗口圆角
/// - 支持鼠标拖拽移动（标题栏区域调用 <see cref="DragMove"/>）
/// - 支持边缘/角落缩放手柄（WM_NCHITTEST）
/// </summary>
public static class WindowChromeHelper
{
    private const int WM_NCHITTEST = 0x0084;
    private const int HTCLIENT = 1;
    private const int HTLEFT = 10;
    private const int HTRIGHT = 11;
    private const int HTTOP = 12;
    private const int HTTOPLEFT = 13;
    private const int HTTOPRIGHT = 14;
    private const int HTBOTTOM = 15;
    private const int HTBOTTOMLEFT = 16;
    private const int HTBOTTOMRIGHT = 17;

    private const int ResizeBorder = 6;

    private static readonly Dictionary<Window, HwndSourceHook> Hooks = new();

    /// <summary>把窗口改为自绘边框样式（圆角 + 无标题栏），并挂载缩放钩子。</summary>
    public static void Apply(Window window, double cornerRadius = 12)
    {
        window.WindowStyle = WindowStyle.None;
        window.ResizeMode = ResizeMode.CanResize;
        window.Background = Brushes.Transparent;
        window.AllowsTransparency = true;
        window.WindowStartupLocation = WindowStartupLocation.CenterScreen;

        // 外层容器必须由各窗口自己提供圆角 Border，这里只保证透明底
        window.Loaded += (_, _) =>
        {
            var handle = new WindowInteropHelper(window).Handle;
            if (handle == IntPtr.Zero) return;
            var source = HwndSource.FromHwnd(handle);
            if (source == null) return;
            var hook = new HwndSourceHook((IntPtr h, int m, IntPtr wParam, IntPtr lParam, ref bool isHandled) =>
                HitTestHook(window, m, wParam, lParam, ref isHandled, cornerRadius));
            source.AddHook(hook);
            Hooks[window] = hook;

            // 最大/还原时移除圆角视觉（贴边不需要圆角，交给窗口内部处理）
            window.StateChanged += (_, _) => window.InvalidateVisual();
        };

        window.Closed += (_, _) =>
        {
            if (Hooks.Remove(window, out var hook))
            {
                var handle = new WindowInteropHelper(window).Handle;
                if (handle != IntPtr.Zero && HwndSource.FromHwnd(handle) is { } s)
                {
                    s.RemoveHook(hook);
                }
            }
        };
    }

    private static IntPtr HitTestHook(
        Window window, int msg, IntPtr wParam, IntPtr lParam, ref bool handled, double cornerRadius)
    {
        if (msg != WM_NCHITTEST || window.WindowState != WindowState.Normal || !window.IsLoaded)
        {
            return IntPtr.Zero;
        }

        // lParam 为屏幕坐标（低字 X，高字 Y）
        var x = lParam.ToInt32() & 0xFFFF;
        var y = (lParam.ToInt32() >> 16) & 0xFFFF;
        var screenPoint = new Point(x, y);
        var clientPoint = window.PointFromScreen(screenPoint);

        // 圆角四角之外视为可穿透（不处理），避免在圆角外出现光标
        var w = window.ActualWidth;
        var h = window.ActualHeight;
        if (w <= 0 || h <= 0) return IntPtr.Zero;

        var left = clientPoint.X <= ResizeBorder;
        var right = clientPoint.X >= w - ResizeBorder;
        var top = clientPoint.Y <= ResizeBorder;
        var bottom = clientPoint.Y >= h - ResizeBorder;

        // 圆角角落区域不做调整（视觉一致）
        var r = cornerRadius;
        var inTopLeftCorner = clientPoint.X < r && clientPoint.Y < r &&
                              Math.Sqrt(Math.Pow(r - clientPoint.X, 2) + Math.Pow(r - clientPoint.Y, 2)) > r;
        var inTopRightCorner = clientPoint.X > w - r && clientPoint.Y < r &&
                               Math.Sqrt(Math.Pow(clientPoint.X - (w - r), 2) + Math.Pow(r - clientPoint.Y, 2)) > r;
        var inBottomLeftCorner = clientPoint.X < r && clientPoint.Y > h - r &&
                                 Math.Sqrt(Math.Pow(r - clientPoint.X, 2) + Math.Pow(clientPoint.Y - (h - r), 2)) > r;
        var inBottomRightCorner = clientPoint.X > w - r && clientPoint.Y > h - r &&
                                  Math.Sqrt(Math.Pow(clientPoint.X - (w - r), 2) + Math.Pow(clientPoint.Y - (h - r), 2)) > r;

        int hit;
        if (inTopLeftCorner || inTopRightCorner || inBottomLeftCorner || inBottomRightCorner)
        {
            return IntPtr.Zero;
        }
        else if (left && top) hit = HTTOPLEFT;
        else if (right && top) hit = HTTOPRIGHT;
        else if (left && bottom) hit = HTBOTTOMLEFT;
        else if (right && bottom) hit = HTBOTTOMRIGHT;
        else if (left) hit = HTLEFT;
        else if (right) hit = HTRIGHT;
        else if (top) hit = HTTOP;
        else if (bottom) hit = HTBOTTOM;
        else return IntPtr.Zero;

        handled = true;
        return (IntPtr)hit;
    }

    /// <summary>让指定元素充当标题栏：左键按住可拖拽窗口，双击可最大化/还原。</summary>
    public static void MakeTitleBar(FrameworkElement element)
    {
        element.MouseLeftButtonDown += (_, e) =>
        {
            var window = Window.GetWindow(element);
            if (window == null) return;

            if (e.ClickCount == 2)
            {
                window.WindowState = window.WindowState == WindowState.Maximized
                    ? WindowState.Normal
                    : WindowState.Maximized;
                return;
            }

            try
            {
                window.DragMove();
            }
            catch (InvalidOperationException)
            {
                // 鼠标按下时窗口未就绪等情况，忽略
            }
        };
    }

    /// <summary>最大化时去掉系统阴影偏移（保持窗口贴边），供外层 Border 触发。</summary>
    public static bool IsMaximized(Window window) => window.WindowState == WindowState.Maximized;
}
