using System.Globalization;
using System.Windows;
using System.Windows.Data;
using System.Windows.Media;
using System.Windows.Media.Imaging;

namespace Komichi.Desktop.Converters;

/// <summary>bool → Visibility（true=Visible, false=Collapsed；参数 invert 时反转）</summary>
public class BoolToVisibilityConverter : IValueConverter
{
    public object Convert(object? value, Type targetType, object? parameter, CultureInfo culture)
    {
        var isTrue = value is true;
        if (parameter is string s && s.Equals("invert", StringComparison.OrdinalIgnoreCase))
        {
            isTrue = !isTrue;
        }
        return isTrue ? Visibility.Visible : Visibility.Collapsed;
    }

    public object ConvertBack(object? value, Type targetType, object? parameter, CultureInfo culture)
        => value is Visibility.Visible;
}

/// <summary>null/空字符串 → 占位文案</summary>
public class NullToPlaceholderConverter : IValueConverter
{
    public object Convert(object? value, Type targetType, object? parameter, CultureInfo culture)
    {
        var text = value as string;
        if (string.IsNullOrWhiteSpace(text))
        {
            return parameter as string ?? "暂无";
        }
        return text;
    }

    public object ConvertBack(object? value, Type targetType, object? parameter, CultureInfo culture)
        => throw new NotSupportedException();
}

/// <summary>作品状态 → 徽章颜色（连载中=品牌绿, 已完结=琥珀, 其他=品牌蓝绿）</summary>
public class StatusToBrushConverter : IValueConverter
{
    public object Convert(object? value, Type targetType, object? parameter, CultureInfo culture)
    {
        return (value as string) switch
        {
            "ongoing" => new SolidColorBrush(Color.FromRgb(0x32, 0xF0, 0x8C)),
            "completed" => new SolidColorBrush(Color.FromRgb(0xDC, 0xB3, 0x64)),
            _ => new SolidColorBrush(Color.FromRgb(0x2D, 0xD2, 0x88)),
        };
    }

    public object ConvertBack(object? value, Type targetType, object? parameter, CultureInfo culture)
        => throw new NotSupportedException();
}

/// <summary>null BitmapImage → 占位图（透明色块上的漫画图标文字）</summary>
public class NullCoverToVisibilityConverter : IValueConverter
{
    public object Convert(object? value, Type targetType, object? parameter, CultureInfo culture)
        => value is BitmapImage ? Visibility.Collapsed : Visibility.Visible;

    public object ConvertBack(object? value, Type targetType, object? parameter, CultureInfo culture)
        => throw new NotSupportedException();
}

/// <summary>字符串非空 → Visible，空/null → Collapsed</summary>
public class StringToVisibilityConverter : IValueConverter
{
    public object Convert(object? value, Type targetType, object? parameter, CultureInfo culture)
        => !string.IsNullOrWhiteSpace(value as string) ? Visibility.Visible : Visibility.Collapsed;

    public object ConvertBack(object? value, Type targetType, object? parameter, CultureInfo culture)
        => throw new NotSupportedException();
}
