using System.Diagnostics;
using System.Drawing.Drawing2D;
using System.Net.Http.Json;
using System.Text;
using System.Text.Json;
using System.Runtime.InteropServices;
using System.Windows.Forms;

namespace CassiCompanion;

internal static class Program
{
    [STAThread]
    private static void Main(string[] args)
    {
        Application.SetHighDpiMode(HighDpiMode.PerMonitorV2);
        Application.EnableVisualStyles();
        Application.SetCompatibleTextRenderingDefault(false);
        try
        {
            int port = 8090;
            string? showShortcut = null;
            string? pauseShortcut = null;
            for (int i = 0; i < args.Length; i++)
            {
                if (args[i] == "--port" && i + 1 < args.Length && int.TryParse(args[++i], out int value) && value is > 0 and <= 65535) port = value;
                else if (args[i] == "--shortcut-show" && i + 1 < args.Length) showShortcut = args[++i];
                else if (args[i] == "--shortcut-pause" && i + 1 < args.Length) pauseShortcut = args[++i];
                else throw new ArgumentException("Use --port <1..65535> [--shortcut-show Ctrl+Alt+S] [--shortcut-pause Ctrl+Alt+P].");
            }
            Application.Run(new CompanionBar(new Uri($"http://127.0.0.1:{port}/"), showShortcut, pauseShortcut));
        }
        catch (Exception error)
        {
            MessageBox.Show(error.Message, "Cassi companion connection", MessageBoxButtons.OK, MessageBoxIcon.Warning);
        }
    }
}

internal sealed class CompanionBar : Form
{
    private static readonly Color Canvas = ColorTranslator.FromHtml("#0d1b19");
    private static readonly Color Jade = ColorTranslator.FromHtml("#72e7be");
    private static readonly Color Ivory = ColorTranslator.FromHtml("#ecf5f2");
    private static readonly Color Sage = ColorTranslator.FromHtml("#adbfba");
    private static readonly Color Amber = ColorTranslator.FromHtml("#e8c47b");
    private static readonly Color Coral = ColorTranslator.FromHtml("#ff8f8f");
    private readonly HttpClient _client;
    private readonly Uri _origin;
    private readonly NotifyIcon _tray;
    private readonly System.Windows.Forms.Timer _timer;
    private readonly Label _state;
    private readonly Label _ages;
    private readonly Button _show;
    private readonly Button _pause;
    private readonly Button _finish;
    private readonly Label _indicator;
    private readonly (uint Modifiers, uint Key)? _showHotkey;
    private readonly (uint Modifiers, uint Key)? _pauseHotkey;
    private bool _showRegistered;
    private bool _pauseRegistered;
    private bool _polling;
    private bool _stopping;
    private string _phase = "Ready";
    private bool _quitting;
    protected override bool ShowWithoutActivation => true;
    private Point _drag;

    public CompanionBar(Uri origin, string? showShortcut, string? pauseShortcut)
    {
        _origin = origin;
        _showHotkey = ParseHotkey(showShortcut);
        _pauseHotkey = ParseHotkey(pauseShortcut);
        if (_showHotkey.HasValue && _showHotkey == _pauseHotkey)
            throw new ArgumentException("Assign different shortcuts to Show and Pause.");
        _client = new HttpClient(new HttpClientHandler { UseCookies = false, UseProxy = false }) {
            BaseAddress = origin, Timeout = TimeSpan.FromSeconds(7)
        };
        Text = "Cassi · beside you";
        AccessibleName = "Cassi companion";
        FormBorderStyle = FormBorderStyle.None;
        ShowInTaskbar = false;
        TopMost = true;
        BackColor = Canvas;
        ForeColor = Ivory;
        DoubleBuffered = true;
        var area = Screen.PrimaryScreen?.WorkingArea ?? new Rectangle(0, 0, 1280, 800);
        Width = Math.Min(565, Math.Max(340, area.Width - 24));
        Height = Width < 510 ? 158 : 118;
        MinimumSize = new Size(340, 118);
        AutoScaleMode = AutoScaleMode.Dpi;
        KeyPreview = true;
        Padding = new Padding(18, 12, 18, 12);
        StartPosition = FormStartPosition.Manual;
        Location = new Point(area.Right - Width - 22, area.Bottom - Height - 22);

        _indicator = new Label { Text = "●", ForeColor = Sage, Font = new Font("Segoe UI", 13),
            Location = new Point(17, 13), Size = new Size(23, 29), AccessibleName = "Observation stopped" };
        var brand = new Label { Text = "Cassi", Font = new Font("Georgia", 15), ForeColor = Ivory,
            Location = new Point(43, 10), Size = new Size(105, 32), Cursor = Cursors.SizeAll };
        _state = new Label { Text = "Ready · connect to Cassi", Font = new Font("Segoe UI", 9.5f, FontStyle.Bold),
            ForeColor = Sage, Location = new Point(154, 17), Size = new Size(390, 21),
            AutoEllipsis = true, Cursor = Cursors.Hand, AccessibleName = "Companion status; open details" };
        _ages = new Label { Text = "Waiting for the entity", ForeColor = Sage,
            Font = new Font("Segoe UI", 8.5f), Location = new Point(44, 45), Size = new Size(485, 22),
            AutoEllipsis = true, AccessibleName = "Capture and interpretation freshness" };
        _show = MakeButton("Show her something", 44, 77, 182, true);
        _show.EnabledChanged += (_, _) => {
            _show.BackColor = _show.Enabled ? Jade : ColorTranslator.FromHtml("#9cb1a7");
            _show.ForeColor = ColorTranslator.FromHtml("#06110d");
        };
        _pause = MakeButton("Pause", 235, 77, 114, false);
        _finish = MakeButton("Finish", 357, 77, 114, false);
        Controls.AddRange([_indicator, brand, _state, _ages, _show, _pause, _finish]);
        ArrangeControls();
        foreach (Control control in new Control[] { this, brand, _indicator, _ages }) {
            control.MouseDown += (_, e) => {
                if (e.Button == MouseButtons.Left)
                    _drag = new Point(Cursor.Position.X - Left, Cursor.Position.Y - Top);
            };
            control.MouseMove += (_, e) => {
                if (e.Button == MouseButtons.Left && _drag != Point.Empty)
                    Location = new Point(Cursor.Position.X - _drag.X, Cursor.Position.Y - _drag.Y);
            };
            control.MouseUp += (_, _) => _drag = Point.Empty;
        }
        _state.Click += (_, _) => OpenDetails();
        _show.Click += (_, _) => OpenDetails("#moment");
        _pause.Click += async (_, _) => await ControlAsync(ResumeState(_phase) ? "resume" : "pause");
        _finish.Click += async (_, _) => await ControlAsync("finish");
        _tray = new NotifyIcon {
            Text = "Cassi · observation stopped", Icon = MakeIcon(), Visible = true,
            ContextMenuStrip = new ContextMenuStrip()
        };
        _tray.ContextMenuStrip.Items.Add("Open companion", null, (_, _) => OpenDetails());
        _tray.ContextMenuStrip.Items.Add("Pause watching", null, async (_, _) => await ControlAsync("pause"));
        _tray.ContextMenuStrip.Items.Add("Finish session", null, async (_, _) => await ControlAsync("finish"));
        _tray.ContextMenuStrip.Items.Add(new ToolStripSeparator());
        _tray.ContextMenuStrip.Items.Add("Quit companion", null, async (_, _) => await QuitAsync());
        _tray.DoubleClick += (_, _) => OpenDetails();
        _timer = new System.Windows.Forms.Timer { Interval = 1600 };
        _timer.Tick += async (_, _) => await RefreshAsync();
        _timer.Start();
        Shown += async (_, _) => { RegisterShortcuts(); await RefreshAsync(); };
        FormClosed += (_, _) => { _timer.Dispose(); _tray.Visible = false; _tray.Dispose(); _client.Dispose(); };
    }

    [DllImport("user32.dll", SetLastError = true)]
    private static extern bool RegisterHotKey(IntPtr window, int id, uint modifiers, uint key);
    [DllImport("user32.dll", SetLastError = true)]
    private static extern bool UnregisterHotKey(IntPtr window, int id);

    private static (uint Modifiers, uint Key)? ParseHotkey(string? text)
    {
        if (text is null) return null;
        string[] pieces = text.Split('+', StringSplitOptions.TrimEntries | StringSplitOptions.RemoveEmptyEntries);
        if (pieces.Length < 2) throw new ArgumentException("A shortcut needs modifiers and one letter or F1–F12.");
        uint modifiers = 0x4000; // MOD_NOREPEAT
        for (int i = 0; i < pieces.Length - 1; i++) {
            uint bit = pieces[i].ToUpperInvariant() switch {
                "CTRL" or "CONTROL" => 0x2,
                "ALT" => 0x1,
                "SHIFT" => 0x4,
                "WIN" => 0x8,
                _ => throw new ArgumentException($"Unknown shortcut modifier: {pieces[i]}")
            };
            if ((modifiers & bit) != 0) throw new ArgumentException("A shortcut modifier is repeated.");
            modifiers |= bit;
        }
        if (!Enum.TryParse<Keys>(pieces[^1], true, out var key)
            || !((key >= Keys.A && key <= Keys.Z) || (key >= Keys.F1 && key <= Keys.F12)))
            throw new ArgumentException("Use one letter or F1–F12 for a shortcut.");
        return (modifiers, (uint)key);
    }

    private void RegisterShortcuts()
    {
        if (_showHotkey is { } show) {
            _showRegistered = RegisterHotKey(Handle, 41, show.Modifiers, show.Key);
            if (!_showRegistered) _tray.ContextMenuStrip!.Items.Insert(0,
                new ToolStripMenuItem("Show shortcut unavailable (already in use)") { Enabled = false });
        }
        if (_pauseHotkey is { } pause) {
            _pauseRegistered = RegisterHotKey(Handle, 42, pause.Modifiers, pause.Key);
            if (!_pauseRegistered) _tray.ContextMenuStrip!.Items.Insert(0,
                new ToolStripMenuItem("Pause shortcut unavailable (already in use)") { Enabled = false });
        }
    }

    protected override void WndProc(ref Message message)
    {
        if (message.Msg == 0x0312) { // WM_HOTKEY; commands are explicitly registered, no key history.
            if (message.WParam.ToInt32() == 41) OpenDetails("#moment");
            else if (message.WParam.ToInt32() == 42 && _pause.Enabled)
                _ = ControlAsync(ResumeState(_phase) ? "resume" : "pause");
            return;
        }
        base.WndProc(ref message);
    }

    protected override void OnHandleDestroyed(EventArgs e)
    {
        if (_showRegistered) { UnregisterHotKey(Handle, 41); _showRegistered = false; }
        if (_pauseRegistered) { UnregisterHotKey(Handle, 42); _pauseRegistered = false; }
        base.OnHandleDestroyed(e);
    }

    private Button MakeButton(string label, int x, int y, int width, bool primary)
    {
        var button = new Button { Text = label, AccessibleName = label, TabStop = true,
            Location = new Point(x, y), Size = new Size(width, 33), FlatStyle = FlatStyle.Flat,
            BackColor = primary ? Jade : ColorTranslator.FromHtml("#19302c"),
            ForeColor = primary ? ColorTranslator.FromHtml("#06110d") : Ivory,
            Font = new Font("Segoe UI", 8.5f, FontStyle.Bold), Cursor = Cursors.Hand };
        button.FlatAppearance.BorderColor = primary ? Jade : ColorTranslator.FromHtml("#47635d");
        return button;
    }

    private static Icon MakeIcon()
    {
        using var bitmap = new Bitmap(32, 32);
        using (Graphics graphics = Graphics.FromImage(bitmap)) {
            graphics.SmoothingMode = SmoothingMode.AntiAlias;
            graphics.Clear(Color.Transparent);
            using var background = new SolidBrush(Canvas);
            using var accent = new Pen(Jade, 2.6f);
            using var dot = new SolidBrush(Jade);
            graphics.FillEllipse(background, 1, 1, 30, 30);
            graphics.DrawEllipse(accent, 4, 4, 23, 23);
            graphics.FillEllipse(dot, 13, 13, 6, 6);
        }
        IntPtr handle = bitmap.GetHicon();
        try {
            using var temporary = Icon.FromHandle(handle);
            return (Icon)temporary.Clone();
        }
        finally { DestroyIcon(handle); }
    }

    private void OpenDetails(string fragment = "")
    {
        Process.Start(new ProcessStartInfo(new Uri(_origin, $"companion/{fragment}").ToString()) { UseShellExecute = true });
    }
    [DllImport("user32.dll")] private static extern bool DestroyIcon(IntPtr handle);

    private static string GetString(JsonElement row, string name, string fallback = "") =>
        row.TryGetProperty(name, out var value) && value.ValueKind == JsonValueKind.String
            ? value.GetString() ?? fallback : fallback;

    private static string Age(JsonElement row, string name)
    {
        if (!row.TryGetProperty(name, out var value) || value.ValueKind != JsonValueKind.Number
            || !value.TryGetInt64(out long milliseconds) || milliseconds < 0) return "—";
        return milliseconds < 1000 ? "now" : $"{milliseconds / 1000}s";
    }

    private static bool ResumeState(string state) =>
        state.Equals("paused", StringComparison.OrdinalIgnoreCase)
        || state.Equals("lease-expired", StringComparison.OrdinalIgnoreCase);

    private static bool InactiveState(string state) =>
        state.Equals("idle", StringComparison.OrdinalIgnoreCase)
        || state.Equals("ready", StringComparison.OrdinalIgnoreCase)
        || state.Equals("finished", StringComparison.OrdinalIgnoreCase);

    private static string DisplayState(string state) => state.ToLowerInvariant() switch {
        "idle" => "Ready to watch",
        "watching" => "Watching",
        "waiting-for-window" => "Waiting for your window",
        "window-unavailable" => "Window unavailable",
        "paused" => "Paused",
        "finishing" => "Finishing",
        "processing" => "Catching up",
        "lease-expired" => "Observation timed out",
        "finished" => "Finished",
        "ready" => "Ready",
        _ => state.Replace('-', ' '),
    };

    private async Task RefreshAsync()
    {
        if (_polling || _stopping || IsDisposed) return;
        _polling = true;
        try {
            using var response = await _client.GetAsync("v1/companion");
            response.EnsureSuccessStatusCode();
            using var document = await response.Content.ReadFromJsonAsync<JsonDocument>();
            if (document is null) throw new HttpRequestException("The entity returned no session state.");
            JsonElement status = document.RootElement;
            string state = GetString(status, "state", "Ready");
            _phase = state;
            string source = GetString(status, "source_label");
            _state.Text = source.Length > 0 ? $"{DisplayState(state)} · {source}" : DisplayState(state);
            _state.AccessibleName = $"{_state.Text}; open details";
            _ages.Text = $"Capture {Age(status, "capture_age_ms")}   ·   Interpretation {Age(status, "interpretation_age_ms")}";
            _ages.AccessibleName = _ages.Text;
            bool active = state.Equals("Watching", StringComparison.OrdinalIgnoreCase)
                || state.Equals("Catching up", StringComparison.OrdinalIgnoreCase);
            _indicator.ForeColor = active ? Jade
                : state.Contains("lost", StringComparison.OrdinalIgnoreCase) || state.Contains("unavailable", StringComparison.OrdinalIgnoreCase) ? Coral
                : state.Contains("wait", StringComparison.OrdinalIgnoreCase) ? Amber : Sage;
            _indicator.AccessibleName = active ? "Desktop observation active" : "Desktop observation stopped or waiting";
            _show.Enabled = active;
            _pause.Text = ResumeState(state) ? "Resume" : "Pause";
            _pause.AccessibleName = _pause.Text;
            _pause.Enabled = active || ResumeState(state)
                || state.Equals("waiting-for-window", StringComparison.OrdinalIgnoreCase)
                || state.Equals("window-unavailable", StringComparison.OrdinalIgnoreCase);
            _finish.Enabled = !InactiveState(state);
            _tray.Text = ($"Cassi · {state}").Length > 63 ? "Cassi companion" : $"Cassi · {state}";
        }
        catch (Exception error) when (error is HttpRequestException or TaskCanceledException or JsonException) {
            _phase = "Connection lost";
            _state.Text = "Connection lost";
            _ages.Text = "Reconnect to confirm observation has stopped";
            _state.AccessibleName = "Connection lost; open details";
            _ages.AccessibleName = _ages.Text;
            _indicator.ForeColor = Coral;
            _pause.Enabled = false;
            _show.Enabled = false;
        }
        finally { _polling = false; }
    }

    private async Task<bool> ControlAsync(string action)
    {
        if (_stopping) return false;
        _stopping = true;
        _state.Text = action == "pause" ? "Pausing…" : action == "finish" ? "Finishing…" : "Resuming…";
        try {
            using var content = new StringContent(JsonSerializer.Serialize(new { action }), Encoding.UTF8, "application/json");
            using var response = await _client.PostAsync("v1/companion/control", content);
            response.EnsureSuccessStatusCode();
            return true;
        }
        catch (Exception error) when (error is HttpRequestException or TaskCanceledException) {
            _state.Text = "Stop not confirmed · inspect connection";
            _indicator.ForeColor = Coral;
            return false;
        }
        finally { _stopping = false; await RefreshAsync(); }
    }

    private async Task QuitAsync()
    {
        if (_stopping) return;
        bool stopped = InactiveState(_phase) || await ControlAsync("finish");
        if (!stopped) {
            var choice = MessageBox.Show(
                "Cassi could not confirm that collection stopped. Retry when the entity reconnects, or quit and rely on the helper's bounded observation lease?",
                "Watching stop not confirmed", MessageBoxButtons.RetryCancel, MessageBoxIcon.Warning);
            if (choice == DialogResult.Retry) return;
        }
        _quitting = true;
        Close();
    }

    protected override void OnFormClosing(FormClosingEventArgs e)
    {
        if (!_quitting && e.CloseReason == CloseReason.UserClosing) {
            e.Cancel = true;
            _ = QuitAsync();
            return;
        }
        base.OnFormClosing(e);
    }

    private void ArrangeControls()
    {
        if (_show is null || _pause is null || _finish is null || _state is null || _ages is null) return;
        int available = Math.Max(246, ClientSize.Width - 62);
        _state.Width = Math.Max(135, ClientSize.Width - 172);
        _ages.Width = Math.Max(200, ClientSize.Width - 62);
        if (ClientSize.Width < 510) {
            if (Height < 148) Height = 158;
            _show.Bounds = new Rectangle(44, 76, available, 33);
            int half = (available - 8) / 2;
            _pause.Bounds = new Rectangle(44, 115, half, 33);
            _finish.Bounds = new Rectangle(52 + half, 115, half, 33);
        } else {
            if (Height > 145) Height = 118;
            int showWidth = Math.Max(172, available - 232);
            _show.Bounds = new Rectangle(44, 77, showWidth, 33);
            _pause.Bounds = new Rectangle(52 + showWidth, 77, 100, 33);
            _finish.Bounds = new Rectangle(160 + showWidth, 77, 116, 33);
        }
    }

    private static GraphicsPath RoundedRectangle(Rectangle bounds, int radius)
    {
        var path = new GraphicsPath();
        int diameter = radius * 2;
        path.AddArc(bounds.Left, bounds.Top, diameter, diameter, 180, 90);
        path.AddArc(bounds.Right - diameter, bounds.Top, diameter, diameter, 270, 90);
        path.AddArc(bounds.Right - diameter, bounds.Bottom - diameter, diameter, diameter, 0, 90);
        path.AddArc(bounds.Left, bounds.Bottom - diameter, diameter, diameter, 90, 90);
        path.CloseFigure();
        return path;
    }

    protected override void OnResize(EventArgs e)
    {
        base.OnResize(e);
        if (Width < 36 || Height < 36) return;
        using var path = RoundedRectangle(new Rectangle(0, 0, Width, Height), 14);
        var previous = Region;
        Region = new Region(path);
        previous?.Dispose();
        ArrangeControls();
    }

    protected override void OnPaint(PaintEventArgs e)
    {
        base.OnPaint(e);
        e.Graphics.SmoothingMode = SmoothingMode.AntiAlias;
        using var path = RoundedRectangle(new Rectangle(1, 1, Width - 3, Height - 3), 14);
        using var border = new Pen(ColorTranslator.FromHtml("#42635a"), 1);
        e.Graphics.DrawPath(border, path);
    }

}
