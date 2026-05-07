using System;
using System.Collections.Generic;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Media;
using System.Windows.Shapes;

namespace HrSRLAdviser
{
    /// <summary>
    /// Pure-C# WPF overlay panel that displays action suggestions on the
    /// HDT overlay canvas. Avoids XAML to sidestep dotnet-build XAML
    /// compilation issues with .NET Framework class libraries.
    /// </summary>
    public class SuggestionOverlay : Border
    {
        private readonly TextBlock _headerText;
        private readonly StackPanel _suggestionsPanel;
        private readonly TextBlock _valueText;
        private readonly TextBlock _rankText;
        private readonly TextBlock _errorText;
        private readonly TextBlock _arrangeText;
        private readonly StackPanel _arrangePanel;

        private readonly SolidColorBrush _goldBrush =
            new SolidColorBrush(Color.FromRgb(0xD4, 0xA0, 0x17));
        private readonly SolidColorBrush _grayBrush =
            new SolidColorBrush(Color.FromRgb(0x88, 0x88, 0x88));
        private readonly SolidColorBrush _whiteBrush =
            new SolidColorBrush(Color.FromRgb(0xE8, 0xE8, 0xE8));
        private readonly SolidColorBrush _blueBrush =
            new SolidColorBrush(Color.FromRgb(0x4A, 0x90, 0xD9));
        private readonly SolidColorBrush _bgBrush =
            new SolidColorBrush(Color.FromArgb(0xF0, 0x08, 0x11, 0x20));
        private readonly SolidColorBrush _separatorBrush =
            new SolidColorBrush(Color.FromArgb(0x33, 0x4A, 0x90, 0xD9));
        private readonly SolidColorBrush _errorBrush =
            new SolidColorBrush(Color.FromRgb(0xFF, 0x6B, 0x41));

        public SuggestionOverlay()
        {
            Width = 280;
            Visibility = Visibility.Collapsed;

            Background = _bgBrush;
            BorderBrush = _blueBrush;
            BorderThickness = new Thickness(1);
            CornerRadius = new CornerRadius(6);
            Padding = new Thickness(12, 10, 12, 10);
            Margin = new Thickness(10);

            HorizontalAlignment = HorizontalAlignment.Left;
            VerticalAlignment = VerticalAlignment.Bottom;

            var rootStack = new StackPanel();

            // Header
            _headerText = new TextBlock
            {
                Text = "HrSRL Adviser",
                FontSize = 14,
                FontWeight = FontWeights.Bold,
                Foreground = _blueBrush,
                Margin = new Thickness(0, 0, 0, 8),
            };
            rootStack.Children.Add(_headerText);

            // Separator 1
            rootStack.Children.Add(CreateSeparator());

            // Suggestions
            _suggestionsPanel = new StackPanel();
            rootStack.Children.Add(_suggestionsPanel);

            // Board arrangement
            _arrangePanel = new StackPanel { Visibility = Visibility.Collapsed };
            var arrangeSep = CreateSeparator(6, 4);
            arrangeSep.Visibility = Visibility.Collapsed;
            _arrangePanel.Children.Add(arrangeSep);
            _arrangeText = new TextBlock
            {
                FontSize = 11,
                Foreground = new SolidColorBrush(Color.FromArgb(0xCC, 0x4A, 0x90, 0xD9)),
                TextWrapping = TextWrapping.Wrap,
                Margin = new Thickness(0, 0, 0, 2),
            };
            _arrangePanel.Children.Add(_arrangeText);
            rootStack.Children.Add(_arrangePanel);

            // Separator 2
            rootStack.Children.Add(CreateSeparator(6, 4));

            // Footer
            var footer = new StackPanel { Orientation = Orientation.Horizontal };
            _valueText = new TextBlock
            {
                FontSize = 11,
                Foreground = new SolidColorBrush(Color.FromArgb(0x88, 0xFF, 0xFF, 0xFF)),
            };
            _rankText = new TextBlock
            {
                FontSize = 11,
                Foreground = _goldBrush,
                Margin = new Thickness(20, 0, 0, 0),
            };
            footer.Children.Add(_valueText);
            footer.Children.Add(_rankText);
            rootStack.Children.Add(footer);

            // Error
            _errorText = new TextBlock
            {
                FontSize = 11,
                Foreground = _errorBrush,
                TextWrapping = TextWrapping.Wrap,
                Visibility = Visibility.Collapsed,
                Margin = new Thickness(0, 4, 0, 0),
            };
            rootStack.Children.Add(_errorText);

            Child = rootStack;

            // Position on overlay canvas when added
            Loaded += (s, e) =>
            {
                if (Parent is Canvas canvas)
                {
                    Canvas.SetLeft(this, 20);
                    Canvas.SetBottom(this, 80);
                }
            };
        }

        public void UpdateSuggestions(SuggestionsMessage suggestions)
        {
            if (suggestions?.actions == null) return;

            Dispatcher.Invoke(() =>
            {
                _suggestionsPanel.Children.Clear();
                _errorText.Visibility = Visibility.Collapsed;

                int i = 0;
                foreach (var a in suggestions.actions)
                {
                    var row = new StackPanel
                    {
                        Orientation = Orientation.Horizontal,
                        Margin = new Thickness(0, 2, 0, 2),
                    };

                    var marker = new TextBlock
                    {
                        Text = i == 0 ? "★" : "☆",
                        Foreground = _goldBrush,
                        FontWeight = FontWeights.Bold,
                        FontSize = 12,
                        Width = 18,
                    };
                    row.Children.Add(marker);

                    var name = new TextBlock
                    {
                        Text = a.name,
                        Foreground = _whiteBrush,
                        FontSize = 12,
                        Width = 160,
                    };
                    row.Children.Add(name);

                    var prob = new TextBlock
                    {
                        Text = (a.probability * 100.0).ToString("F1") + "%",
                        Foreground = _grayBrush,
                        FontSize = 11,
                        HorizontalAlignment = HorizontalAlignment.Right,
                    };
                    row.Children.Add(prob);

                    _suggestionsPanel.Children.Add(row);
                    i++;
                }

                // Board arrangement
                if (suggestions.rearrangement != null &&
                    suggestions.rearrangement.Count >= 2)
                {
                    var parts = new List<string>();
                    foreach (var idx in suggestions.rearrangement)
                        parts.Add("[" + idx + "]");
                    _arrangeText.Text = "Board: " + string.Join(" → ", parts);
                    _arrangePanel.Visibility = Visibility.Visible;
                }
                else
                {
                    _arrangePanel.Visibility = Visibility.Collapsed;
                }

                double val = suggestions.value_estimate;
                _valueText.Text = "Est. value: " + (val >= 0 ? "+" : "") + val.ToString("F1");

                int rank = suggestions.predicted_rank;
                _rankText.Text = rank switch
                {
                    1 => "Pred: 1st",
                    2 => "Pred: 2nd",
                    3 => "Pred: 3rd",
                    _ => "Pred: " + rank + "th",
                };
                _rankText.Foreground = rank <= 4 ? _goldBrush : _grayBrush;

                Visibility = Visibility.Visible;
            });
        }

        public void ShowError(string message)
        {
            Dispatcher.Invoke(() =>
            {
                Visibility = Visibility.Visible;
                _errorText.Visibility = Visibility.Visible;
                _errorText.Text = "Error: " + message;
                _suggestionsPanel.Children.Clear();
                _valueText.Text = "";
                _rankText.Text = "";
            });
        }

        public void Clear()
        {
            Dispatcher.Invoke(() =>
            {
                Visibility = Visibility.Collapsed;
                _suggestionsPanel.Children.Clear();
            });
        }

        private Rectangle CreateSeparator(int marginTop = 6, int marginBottom = 6)
        {
            return new Rectangle
            {
                Height = 1,
                Fill = _separatorBrush,
                Margin = new Thickness(0, marginTop, 0, marginBottom),
            };
        }
    }
}
