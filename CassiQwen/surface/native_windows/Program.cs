using System.Collections.Concurrent;
using System.Diagnostics;
using System.Globalization;
using System.IO;
using System.IO.Pipes;
using System.Runtime.InteropServices;
using System.Security.Cryptography;
using System.Security.Principal;
using System.Text;
using System.Text.Json;
using System.Windows.Automation;
using Windows.Graphics;
using Windows.Graphics.Capture;
using Windows.Graphics.DirectX;
using Windows.Graphics.DirectX.Direct3D11;
using Windows.Graphics.Imaging;
using Windows.Foundation;
using WinRT;

internal static class Program
{
    private const int MaxHeaderBytes = 1 << 20;
    private const int MaxFrameBytes = 64 << 20;
    private const int MaxSide = 8192;
    private const int MaxTreeNodes = 256;
    private const int MaxTreeDepth = 8;
    private const int MaxTreeTextChars = 16_384;
    private const int MaxNodeTextChars = 1_024;
    private const int MaxInputEvents = 128;
    private const int MaxDemonstrationEvents = 256;
    private const int MaxDemonstrationScopes = 32;
    private const uint PipeOptionsCurrentUserOnly = 0x20000000;

    private static readonly string EnvironmentIncarnation = Guid.NewGuid().ToString("N");
    private static readonly byte[] SourceKey = RandomNumberGenerator.GetBytes(32);
    private static readonly object StateLock = new();
    private static readonly Dictionary<string, SourceIdentity> Catalog = new(StringComparer.Ordinal);
    private static readonly Dictionary<string, BoundSource> Bindings = new(StringComparer.Ordinal);
    private static readonly Dictionary<string, string> SourceInstances = new(StringComparer.Ordinal);
    private static readonly EventMonitor Events = new();
    private static readonly string UserSid = WindowsIdentity.GetCurrent().User?.Value ?? "unknown";
    private static readonly int SessionId = Process.GetCurrentProcess().SessionId;
    private static readonly int ProcessId = Environment.ProcessId;
    private static readonly long QpcFrequency = Stopwatch.Frequency;
    private static readonly string BackendVersion = typeof(Program).Assembly.GetName().Version?.ToString() ?? "unknown";
    private static bool DpiPhysical;
    private static bool CaptureSupported;
    private static IDirect3DDevice? D3DDevice;
    private static string? D3DCreateFailure;
    private static ulong InjectionCookie = BitConverter.ToUInt64(RandomNumberGenerator.GetBytes(8));

    public static int Main(string[] args)
    {
        if (!OperatingSystem.IsWindows() || SessionId == 0 || args.Length != 2 || string.IsNullOrWhiteSpace(args[0]) ||
            !int.TryParse(args[1], NumberStyles.None, CultureInfo.InvariantCulture, out int parentPid) || parentPid <= 0)
            return 2;
        int winrtInit = RoInitialize(1);
        if (winrtInit < 0)
            return 2;
        DpiPhysical = SetPhysicalDpiAwareness();
        CaptureSupported = QueryCaptureSupport();
        D3DDevice = CaptureSupported ? CreateD3DDevice() : null;

        try
        {
            Events.Start();
            using var pipe = new NamedPipeServerStream(
                args[0], PipeDirection.InOut, 1, PipeTransmissionMode.Byte,
                (PipeOptions)PipeOptionsCurrentUserOnly);
            pipe.WaitForConnection();
            if (!AuthenticateClient(pipe, parentPid, out string? authReason))
                return 3;
            while (pipe.IsConnected)
            {
                byte[]? requestBytes = ReadMessage(pipe);
                if (requestBytes is null)
                    break;
                using JsonDocument request = JsonDocument.Parse(requestBytes);
                JsonElement root = request.RootElement;
                string op = GetString(root, "op") ?? "";
                object? binary = null;
                Dictionary<string, object?> response;
                try
                {
                    (response, binary) = Handle(op, root);
                }
                catch (Exception ex)
                {
                    response = Error("unavailable", SafeMessage(ex));
                }
                WriteMessage(pipe, response, binary as byte[] ?? Array.Empty<byte>());
                if (op == "close")
                    break;
            }
        }
        catch (IOException)
        {
            // A disconnected authenticated client is a lifecycle event, not a reason to restart it.
        }
        finally
        {
            Events.Stop();
            foreach (BoundSource binding in Bindings.Values)
            {
                try { Neutralize(binding, requireBinding: false); }
                catch { }
                binding.Dispose();
            }
            Bindings.Clear();
            RoUninitialize();
        }
        return 0;
    }

    private static (Dictionary<string, object?>, object?) Handle(string op, JsonElement root)
    {
        switch (op)
        {
            case "hello":
                if (SessionId == 0)
                    return (Error("denied", "Session 0 is not an authorized interactive session"), null);
                return (Ok(("identity", (object)new Dictionary<string, object?>
                {
                    ["user_sid"] = UserSid,
                    ["session_id"] = SessionId,
                    ["process_id"] = ProcessId,
                    ["environment_incarnation"] = EnvironmentIncarnation,
                    ["input_desktop"] = CurrentInputDesktop(),
                    ["window_station"] = ProcessWindowStation(),
                    ["client_authenticated"] = true,
                })), null);
            case "describe":
                return (Ok(("description", (object)Describe())), null);
            case "sources":
                return (Ok(("sources", (object)EnumerateSources())), null);
            case "bind":
                return (Ok(("binding", (object)Bind(RequiredString(root, "source_id")))), null);
            case "foreground_binding":
                return (Ok(("foreground_binding", (object)ForegroundBinding(RequiredObject(root, "binding")))), null);
            case "set_follow_foreground":
                return (Ok(("follow_foreground", (object)SetFollowForeground(
                    RequiredObject(root, "binding"), RequiredBoolean(root, "enabled")))), null);
            case "set_demonstration":
                return (Ok(("demonstration", (object)SetDemonstration(
                    RequiredObject(root, "binding"), RequiredBoolean(root, "enabled")))), null);
            case "unbind":
                return (Ok(("unbound", (object)Unbind(RequiredObject(root, "binding")))), null);
            case "capture":
                return HandleCapture(RequiredObject(root, "binding"));
            case "revalidate_target":
                return (Ok(("target_validation", (object)RevalidateTarget(
                    RequiredObject(root, "binding"), RequiredObject(root, "semantic_target")))), null);
            case "revalidate":
                return (Ok(("revalidation", (object)RevalidateBinding(RequiredObject(root, "binding")))), null);
            case "dispatch":
                return (Ok(("dispatch", (object)Dispatch(RequiredObject(root, "binding"), RequiredObject(root, "action")))), null);
            case "neutralize":
                return (Ok(("neutralize", (object)Neutralize(FindBinding(RequiredObject(root, "binding")), requireBinding: true))), null);
            case "close":
                foreach (BoundSource binding in Bindings.Values)
                    Neutralize(binding, requireBinding: false);
                return (Ok(), null);
            default:
                return (Error("invalid_request", "unknown native helper operation"), null);
        }
    }

    private static Dictionary<string, object?> Describe()
    {
        bool inputDesktop = IsInputDesktopUsable();
        string desktopReason = inputDesktop ? "" : "the current input desktop is not WinSta0\\Default";
        bool visualReady = CaptureSupported && D3DDevice is not null;
        string graphicsReason = !CaptureSupported
            ? "Windows.Graphics.Capture reports unsupported"
            : D3DDevice is null ? D3DCreateFailure ?? "hardware Direct3D 11 device is unavailable" : "";
        string dpiReason = DpiPhysical ? "" : "per-monitor physical-pixel awareness could not be established";
        var capabilities = new Dictionary<string, object?>
        {
            ["visual.window"] = Capability(visualReady ? "supported" : "unavailable", graphicsReason,
                ("formats", new[] { "BGRA8" }), ("max_side", MaxSide), ("max_frame_bytes", MaxFrameBytes),
                ("cursor", "included"), ("capture_border", "system-controlled; never suppressed"),
                ("color_space", "BGRA8 SDR; HDR preservation unavailable")),
            ["visual.display"] = Capability(visualReady ? "supported" : "unavailable", graphicsReason,
                ("formats", new[] { "BGRA8" }), ("max_side", MaxSide), ("max_frame_bytes", MaxFrameBytes),
                ("cursor", "included"), ("capture_border", "system-controlled; never suppressed"),
                ("color_space", "BGRA8 SDR; HDR preservation unavailable")),
            ["binding.revalidate"] = Capability("supported", "", ("refreshes", "existing source and geometry/input/focus capability state; never rebinds")),
            ["accessibility.tree"] = Capability("supported", "", ("provider", "Windows UI Automation"),
                ("max_nodes", MaxTreeNodes), ("max_depth", MaxTreeDepth), ("per_call_timeout_ms", 600),
                ("content_values", "not read"), ("content_text", "bounded TextPattern on non-password edit/document nodes where supported")),
            ["semantic_target.revalidate"] = Capability("supported", "", ("provider", "Windows UI Automation"),
                ("target", "runtime_id observed in the latest snapshot and found in the live bound-window tree"),
                ("per_call_timeout_ms", 600)),
            ["accessibility.invoke"] = Capability("supported", "", ("ack_strength", "provider_call_returned")),
            ["accessibility.set_value"] = Capability("supported", "", ("ack_strength", "provider_call_returned"),
                ("password_controls", "not supported")),
            ["accessibility.select"] = Capability("supported", "", ("ack_strength", "provider_call_returned")),
            ["accessibility.toggle"] = Capability("supported", "", ("ack_strength", "provider_call_returned")),
            ["accessibility.expand"] = Capability("supported", "", ("ack_strength", "provider_call_returned")),
            ["accessibility.focus"] = Capability("supported", "", ("ack_strength", "provider_call_returned")),
            ["keyboard.key"] = Capability(inputDesktop ? "supported" : "unavailable", desktopReason,
                ("key_identity", "Windows virtual-key code"), ("max_events", MaxInputEvents),
                ("focus", "target root or descendant must be foreground"), ("ack_strength", "SendInput insertion count")),
            ["keyboard.text"] = Capability(inputDesktop ? "supported" : "unavailable", desktopReason,
                ("encoding", "UTF-16 Unicode SendInput; layout-independent code units"),
                ("max_utf16_units", MaxInputEvents / 2), ("ack_strength", "SendInput insertion count")),
            ["pointer.absolute"] = Capability(inputDesktop && DpiPhysical ? "supported" : "unavailable",
                !inputDesktop ? desktopReason : dpiReason, ("coordinates", "source-local physical pixels"),
                ("ack_strength", "SendInput insertion count")),
            ["pointer.relative"] = Capability(inputDesktop ? "supported" : "unavailable", desktopReason,
                ("coordinates", "relative screen-pixel movement"), ("ack_strength", "SendInput insertion count")),
            ["pointer.button"] = Capability(inputDesktop ? "supported" : "unavailable", desktopReason,
                ("buttons", new[] { "left", "middle", "right" }), ("ack_strength", "SendInput insertion count")),
            ["pointer.wheel"] = Capability(inputDesktop ? "supported" : "unavailable", desktopReason,
                ("units", "120-unit Windows wheel notches"), ("ack_strength", "SendInput insertion count")),
            ["audio.capture"] = Capability("unavailable", "no Windows audio endpoint is provisioned by this helper"),
            ["clipboard"] = Capability("unavailable", "content transfer is a separately authorized mechanism, not a SendInput fallback"),
            ["touch"] = Capability("unavailable", "no touch contact injector is implemented"),
            ["pen"] = Capability("unavailable", "no pen endpoint is implemented"),
            ["controller"] = Capability("unavailable", "no controller endpoint is implemented"),
            ["physical_input_events"] = Capability(Events.InputHooksAvailable ? "supported" : "unavailable",
                Events.InputHooksAvailable ? "" : "low-level physical-input hooks could not be installed"),
        };
        return new Dictionary<string, object?>
        {
            ["backend_id"] = "windows-native",
            ["environment_incarnation"] = EnvironmentIncarnation,
            ["user_sid"] = UserSid,
            ["session_id"] = SessionId,
            ["helper_process_id"] = ProcessId,
            ["input_desktop"] = CurrentInputDesktop(),
            ["window_station"] = ProcessWindowStation(),
            ["status"] = inputDesktop ? "available" : "degraded",
            ["capabilities"] = capabilities,
            ["limitations"] = new[]
            {
                "Capture uses Windows Graphics Capture frames, never GDI/PrintWindow screenshots.",
                "Capture is BGRA8 SDR only; HDR and protected surfaces are not claimed.",
                "UI Automation calls use a bounded worker; a provider timeout disables further UIA calls for that source.",
                "SendInput insertion is not application acceptance or task completion.",
                "No capture border is suppressed and no picker/consent boundary is bypassed.",
            },
        };
    }

    private static Dictionary<string, object?> Capability(string status, string reason, params (string key, object? value)[] values)
    {
        var result = new Dictionary<string, object?> { ["status"] = status, ["reason"] = string.IsNullOrEmpty(reason) ? null : reason };
        foreach ((string key, object? value) in values)
            result[key] = value;
        return result;
    }

    private static List<Dictionary<string, object?>> EnumerateSources()
    {
        if (SessionId == 0)
            throw new InvalidOperationException("Session 0 cannot enumerate interactive sources");
        var seen = new HashSet<string>(StringComparer.Ordinal);
        var result = new List<Dictionary<string, object?>>();
        EnumWindows((hwnd, unusedState) =>
        {
            try
            {
                if (!IsWindowVisible(hwnd))
                    return true;
                GetWindowThreadProcessId(hwnd, out uint pidValue);
                int pid = checked((int)pidValue);
                if (pid <= 0 || pid == ProcessId || !TryIdentity(hwnd, pid, out SourceIdentity? identity, out _))
                    return true;
                string id = SourceId(identity!);
                seen.Add(id);
                Catalog[id] = identity!;
                var item = SourceDescription(id, identity!);
                result.Add(item);
            }
            catch { }
            return true;
        }, IntPtr.Zero);

        EnumDisplayMonitors(IntPtr.Zero, IntPtr.Zero, (monitor, _, _, _) =>
        {
            try
            {
                if (!TryMonitor(monitor, out SourceIdentity? identity))
                    return true;
                string id = SourceId(identity!);
                seen.Add(id);
                Catalog[id] = identity!;
                result.Add(SourceDescription(id, identity!));
            }
            catch { }
            return true;
        }, IntPtr.Zero);

        foreach (string stale in Catalog.Keys.Where(key => !seen.Contains(key)).ToArray())
            Catalog.Remove(stale);
        foreach (string stale in Bindings.Where(entry => !seen.Contains(entry.Value.SourceId)).Select(entry => entry.Key).ToArray())
        {
            if (Bindings.TryGetValue(stale, out BoundSource? binding))
                binding.MarkLost("source disappeared from the interactive session");
        }
        foreach (string stale in SourceInstances.Keys.Where(key => !seen.Contains(key)).ToArray())
            SourceInstances.Remove(stale);
        result.Sort((left, right) => string.CompareOrdinal((string)left["label"]!, (string)right["label"]!));
        return result;
    }

    private static Dictionary<string, object?> SourceDescription(string sourceId, SourceIdentity identity)
    {
        bool protectedCapture = identity.IsWindow && IsProtectedCaptureWindow(identity.Hwnd);
        bool visible = !identity.IsWindow || IsWindowVisible(identity.Hwnd);
        bool minimized = identity.IsWindow && IsIconic(identity.Hwnd);
        bool inputDesktop = IsInputDesktopUsable();
        bool captureAvailable = CaptureSupported && D3DDevice is not null && inputDesktop && !protectedCapture && visible && !minimized;
        BoundSource? bound = Bindings.Values.FirstOrDefault(item =>
            item.SourceId == sourceId && !item.Lost && item.Identity.Hwnd == identity.Hwnd &&
            item.Identity.ProcessId == identity.ProcessId);
        bool accessibilityAvailable = bound is not null && AccessibilityLive(bound);
        string captureReason = !inputDesktop ? "the active input desktop is unavailable" :
            !CaptureSupported ? "Windows Graphics Capture is unavailable" :
            D3DDevice is null ? D3DCreateFailure ?? "hardware Direct3D 11 device is unavailable" :
            protectedCapture ? "Windows reports capture exclusion/protection for this source" :
            !visible ? "window is not visible" : minimized ? "window is minimized; no fresh image is assumed" : "";
        string accessibilityReason = !identity.IsWindow ? "UI Automation is window-scoped" :
            !inputDesktop ? "the active input desktop is unavailable" :
            protectedCapture ? "capture-excluded windows are not exposed through UI Automation" :
            !visible ? "window is not visible" : minimized ? "window is minimized" :
            bound is null ? "bind the window to verify a live, source-matched UI Automation provider" :
            bound.UiaTimedOut ? "UI Automation was disabled after a provider timeout" :
            "UI Automation is not live for this source";
        var modalities = new List<string>();
        if (captureAvailable)
            modalities.Add("pixels");
        if (accessibilityAvailable)
            modalities.Add("accessibility");
        return new Dictionary<string, object?>
        {
            ["source_id"] = sourceId,
            ["kind"] = identity.IsWindow ? "window" : "display",
            ["label"] = identity.IsWindow ? identity.Title : identity.DisplayName,
            ["title"] = identity.IsWindow ? identity.Title : null,
            ["process_name"] = identity.ProcessName,
            ["process_id"] = identity.IsWindow ? identity.ProcessId : null,
            ["window_class"] = identity.IsWindow ? identity.ClassName : null,
            ["session_id"] = identity.SessionId,
            ["visible"] = visible,
            ["minimized"] = minimized,
            ["protected_or_excluded"] = protectedCapture,
            ["bounds"] = Bounds(identity.Left, identity.Top, identity.Width, identity.Height),
            ["dpi"] = identity.Dpi,
            ["source_instance"] = bound?.SourceInstance ?? EnsureSourceInstance(sourceId),
            ["environment_incarnation"] = EnvironmentIncarnation,
            ["source_epoch"] = bound?.SourceEpoch ?? 1L,
            ["geometry_revision"] = bound?.GeometryRevision ?? 1L,
            ["width"] = bound?.Width ?? identity.Width,
            ["height"] = bound?.Height ?? identity.Height,
            ["modalities"] = modalities,
            ["capture"] = Capability(captureAvailable ? "available" : "unavailable", captureReason),
            ["accessibility"] = Capability(accessibilityAvailable ? "available" : identity.IsWindow && bound is null ? "conditional" : "unavailable",
                accessibilityAvailable ? "" : accessibilityReason),
            ["input"] = Capability(inputDesktop ? "conditional" : "unavailable",
                inputDesktop ? "requires a final target-focus check and broker lease" : "input desktop is not WinSta0\\Default"),
        };
    }
    private static bool AccessibilityLive(BoundSource source)
    {
        if (source.FollowForeground && !IsForegroundSource(source.Identity))
            return false;
        if (source.Lost || source.UiaTimedOut || !source.UiaAvailable || !source.Identity.IsWindow ||
            source.Identity.SessionId != SessionId || !IsInputDesktopUsable() ||
            !IsWindow(source.Identity.Hwnd) || !IsWindowVisible(source.Identity.Hwnd) ||
            IsIconic(source.Identity.Hwnd) || IsProtectedCaptureWindow(source.Identity.Hwnd))
            return false;
        return IdentityStillCurrent(source.Identity, out _);
    }

    private static bool ProbeAccessibility(BoundSource source)
    {
        source.UiaAvailable = false;
        if ((source.FollowForeground && !IsForegroundSource(source.Identity)) ||
            source.UiaTimedOut || source.Lost || !source.Identity.IsWindow ||
            source.Identity.SessionId != SessionId || !IsInputDesktopUsable() ||
            !IsWindow(source.Identity.Hwnd) || !IsWindowVisible(source.Identity.Hwnd) ||
            IsIconic(source.Identity.Hwnd) || IsProtectedCaptureWindow(source.Identity.Hwnd))
            return false;
        IntPtr hwnd = source.Identity.Hwnd;
        int processId = source.Identity.ProcessId;
        var outcome = RunUiaBounded(() => AutomationElement.FromHandle(hwnd).Current.ProcessId == processId, 600);
        if (outcome.TimedOut)
        {
            source.UiaTimedOut = true;
            source.NodeRuntimeIds.Clear();
            return false;
        }
        if (outcome.Error is not null || outcome.Value != true)
        {
            source.NodeRuntimeIds.Clear();
            return false;
        }
        if (!IdentityStillCurrent(source.Identity, out string reason))
        {
            source.MarkLost($"UI Automation source changed during liveness check: {reason}");
            return false;
        }
        source.UiaAvailable = true;
        return true;
    }


    private static Dictionary<string, object?> Bind(string sourceId)
    {
        if (!Catalog.TryGetValue(sourceId, out SourceIdentity? identity))
            throw new InvalidOperationException("source id is not present in the current authenticated-session inventory");
        if (!IdentityStillCurrent(identity, out string reason))
            throw new InvalidOperationException($"source is stale or inaccessible: {reason}; enumerate and bind again");
        BoundSource? source = Bindings.Values.FirstOrDefault(item => item.SourceId == sourceId && !item.Lost);
        if (source is null)
        {
            source = new BoundSource(sourceId, identity, EnvironmentIncarnation, Events, EnsureSourceInstance(sourceId));
        }
        UpdateGeometry(source);
        if (identity.IsWindow)
        {
            try
            {
                source.Item ??= CreateWindowCaptureItem(source.Identity.Hwnd);
                SizeInt32 itemSize = source.Item.Size;
                if (ValidSize(itemSize.Width, itemSize.Height))
                {
                    source.SetCapturedSize(itemSize.Width, itemSize.Height);
                    source.CaptureUnavailable = null;
                }
                else
                {
                    source.CaptureUnavailable = $"WGC returned unsupported content size {itemSize.Width}x{itemSize.Height}";
                }
            }
            catch (Exception ex)
            {
                source.CaptureUnavailable = $"Windows Graphics Capture item creation failed: {SafeMessage(ex)}";
            }
        }
        else
        {
            try
            {
                source.Item ??= CreateMonitorCaptureItem(source.Identity.Monitor);
                SizeInt32 itemSize = source.Item.Size;
                if (ValidSize(itemSize.Width, itemSize.Height))
                {
                    source.SetCapturedSize(itemSize.Width, itemSize.Height);
                    source.CaptureUnavailable = null;
                }
                else
                    source.CaptureUnavailable = $"WGC returned unsupported display size {itemSize.Width}x{itemSize.Height}";
            }
            catch (Exception ex)
            {
                source.CaptureUnavailable = $"Windows Graphics Capture item creation failed: {SafeMessage(ex)}";
            }
        }
        ProbeAccessibility(source);
        Bindings[source.SourceInstance] = source;
        return BindingDescription(source);
    }
    private static Dictionary<string, object?>? CaptureAccessibility(BoundSource source) =>
        source.Identity.IsWindow && source.UiaAvailable && !source.UiaTimedOut &&
            (!source.FollowForeground || IsForegroundSource(source.Identity)) ? AccessibilitySnapshot(source) : null;

    private static Dictionary<string, object?> BindingDescription(BoundSource source)
    {
        var humanState = Events.HumanState(source.Identity);
        bool inputDesktop = IsInputDesktopUsable();
        bool inputAvailable = !source.Lost && inputDesktop && Events.InputHooksAvailable && !humanState.Active;
        string inputReason = source.Lost ? source.LossReason ?? "source is lost" :
            !inputDesktop ? "the active input desktop is unavailable" :
            !Events.InputHooksAvailable ? "physical-input takeover hooks are unavailable" :
            humanState.Active ? "non-injected input was observed recently; human control has priority" : "";
        bool protectedCapture = source.Identity.IsWindow && IsProtectedCaptureWindow(source.Identity.Hwnd);
        bool visible = !source.Identity.IsWindow || IsWindowVisible(source.Identity.Hwnd);
        bool minimized = source.Identity.IsWindow && IsIconic(source.Identity.Hwnd);
        bool foregroundAvailable = !source.FollowForeground || IsForegroundSource(source.Identity);
        bool captureLive = !source.Lost && inputDesktop && foregroundAvailable && CaptureSupported && D3DDevice is not null &&
            source.Item is not null && source.CaptureUnavailable is null && !protectedCapture && visible && !minimized;
        bool accessibilityLive = AccessibilityLive(source);
        string captureReason = source.Lost ? source.LossReason ?? "source is lost" :
            source.FollowForeground && !foregroundAvailable ? "bound foreground source is no longer active" :
            !inputDesktop ? "the active input desktop is unavailable" :
            !CaptureSupported ? "Windows Graphics Capture is unavailable" :
            D3DDevice is null ? D3DCreateFailure ?? "hardware Direct3D 11 device is unavailable" :
            source.CaptureUnavailable ?? (source.Item is null ? "Windows Graphics Capture item is unavailable" :
            protectedCapture ? "Windows reports capture exclusion/protection for this source" :
            !visible ? "window is not visible" : minimized ? "window is minimized; no fresh image is assumed" : "");
        var modalities = new List<string>();
        if (captureLive)
            modalities.Add("pixels");
        if (accessibilityLive)
            modalities.Add("accessibility");
        var operations = new List<string> { "keyboard.key", "keyboard.text", "pointer.relative", "pointer.button", "pointer.wheel" };
        if (DpiPhysical)
            operations.Add("pointer.absolute");
        if (accessibilityLive)
            operations.AddRange(new[] { "accessibility.invoke", "accessibility.set_value", "accessibility.select", "accessibility.toggle", "accessibility.expand", "accessibility.focus" });
        return new Dictionary<string, object?>
        {
            ["backend_id"] = "windows-native",
            ["source_id"] = source.SourceId,
            ["backend_version"] = BackendVersion,
            ["input_domain"] = $"windows-session:{SessionId}:{UserSid}",
            ["focus_epoch"] = Events.FocusEpoch,
            ["source_instance"] = source.SourceInstance,
            ["source_epoch"] = source.SourceEpoch,
            ["environment_incarnation"] = EnvironmentIncarnation,
            ["input_domain_epoch"] = humanState.Epoch,
            ["geometry_revision"] = source.GeometryRevision,
            ["width"] = source.Width,
            ["height"] = source.Height,
            ["modalities"] = modalities,
            ["operations"] = operations,
            ["capture_state"] = captureLive ? "available" : "unavailable",
            ["capture_reason"] = captureLive ? null : captureReason,
            ["follow_foreground"] = source.FollowForeground,
            ["demonstration"] = source.Demonstration,
            ["foreground_available"] = foregroundAvailable,
            ["input_state"] = inputAvailable ? "available" : source.Lost || !IsInputDesktopUsable() || !Events.InputHooksAvailable ? "unavailable" : "suspended",
            ["input_reason"] = inputAvailable ? null : inputReason,
            ["source_kind"] = source.Identity.IsWindow ? "window" : "display",
            ["bounds"] = Bounds(source.Identity.Left, source.Identity.Top, source.Identity.Width, source.Identity.Height),
            ["coordinate_space"] = DpiPhysical ? "source-local-physical-pixels" : "capture-pixels; pointer absolute unavailable",
            ["capture_border"] = "system-controlled",
        };
    }

    private static bool IsForegroundSource(SourceIdentity identity)
    {
        if (!IsInputDesktopUsable())
            return false;
        IntPtr foreground = GetForegroundWindow();
        IntPtr root = foreground == IntPtr.Zero ? IntPtr.Zero : GetAncestor(foreground, GA_ROOT);
        if (root == IntPtr.Zero)
            root = foreground;
        if (identity.IsWindow)
            return root == identity.Hwnd || foreground == identity.Hwnd ||
                (identity.Hwnd != IntPtr.Zero && foreground != IntPtr.Zero && IsChild(identity.Hwnd, foreground));
        if (root == IntPtr.Zero || !GetWindowRect(root, out RECT foregroundRect))
            return false;
        return foregroundRect.Left < identity.Left + identity.Width && foregroundRect.Right > identity.Left
            && foregroundRect.Top < identity.Top + identity.Height && foregroundRect.Bottom > identity.Top;
    }

    private static Dictionary<string, object?> ForegroundBinding(JsonElement bindingJson)
    {
        BoundSource source = FindBinding(bindingJson);
        bool foreground = !source.Lost && IsForegroundSource(source.Identity);
        return new Dictionary<string, object?>
        {
            ["foreground"] = foreground,
            ["source_instance"] = source.SourceInstance,
            ["focus_epoch"] = Events.FocusEpoch,
        };
    }

    private static Dictionary<string, object?> SetFollowForeground(JsonElement bindingJson, bool enabled)
    {
        BoundSource source = FindBinding(bindingJson);
        if (!enabled)
        {
            Dictionary<string, object?> demonstration = SetDemonstration(bindingJson, false);
            if (demonstration.GetValueOrDefault("confirmed") is not true)
                return new Dictionary<string, object?> { ["confirmed"] = false, ["enabled"] = false };
            source.FollowForeground = false;
            return new Dictionary<string, object?>
            {
                ["confirmed"] = true, ["enabled"] = false, ["source_instance"] = source.SourceInstance,
                ["demonstration"] = demonstration,
            };
        }
        if (!EnsureCurrent(source, bindingJson, requireGeometry: false, out string error))
            return new Dictionary<string, object?> { ["confirmed"] = false, ["enabled"] = false, ["reason"] = error };
        source.FollowForeground = true;
        return new Dictionary<string, object?>
        {
            ["confirmed"] = true, ["enabled"] = true, ["source_instance"] = source.SourceInstance,
            ["focus_epoch"] = Events.FocusEpoch,
        };
    }

    private static Dictionary<string, object?> SetDemonstration(JsonElement bindingJson, bool enabled)
    {
        BoundSource source = FindBinding(bindingJson);
        if (!enabled)
        {
            var stopped = Events.RemoveDemonstration(source);
            source.Demonstration = false;
            return new Dictionary<string, object?>
            {
                ["confirmed"] = true, ["enabled"] = false, ["source_instance"] = source.SourceInstance,
                ["events"] = stopped.Events, ["coverage"] = stopped.Coverage,
            };
        }
        if (!source.FollowForeground || source.Lost || !Events.InputHooksAvailable)
            return new Dictionary<string, object?>
            {
                ["confirmed"] = false, ["enabled"] = false,
                ["reason"] = !source.FollowForeground
                    ? "demonstration requires an active bound foreground gate"
                    : "foreground-scoped physical input hooks are unavailable",
            };
        if (!EnsureCurrent(source, bindingJson, requireGeometry: false, out string error))
            return new Dictionary<string, object?> { ["confirmed"] = false, ["enabled"] = false, ["reason"] = error };
        if (!Events.EnableDemonstration(source))
            return new Dictionary<string, object?>
            {
                ["confirmed"] = false, ["enabled"] = false,
                ["reason"] = "bounded demonstration event scope could not be enabled",
            };
        return new Dictionary<string, object?>
        {
            ["confirmed"] = true, ["enabled"] = true, ["source_instance"] = source.SourceInstance,
            ["geometry_revision"] = source.GeometryRevision,
            ["coverage"] = Events.DemonstrationStatus(source),
        };
    }

    private static Dictionary<string, object?> Unbind(JsonElement bindingJson)
    {
        BoundSource source = FindBinding(bindingJson);
        Dictionary<string, object?> stop = SetFollowForeground(bindingJson, false);
        if (stop.GetValueOrDefault("confirmed") is not true)
            return new Dictionary<string, object?> { ["unbound"] = false, ["source_instance"] = source.SourceInstance };
        Dictionary<string, object?> neutralization = Neutralize(source, requireBinding: false);
        if (neutralization.GetValueOrDefault("confirmed") is not true)
            return new Dictionary<string, object?> { ["unbound"] = false, ["neutralization"] = neutralization };
        source.Dispose();
        Bindings.Remove(source.SourceInstance);
        return new Dictionary<string, object?>
        {
            ["unbound"] = true, ["source_instance"] = source.SourceInstance,
            ["demonstration"] = stop.GetValueOrDefault("demonstration"),
        };
    }

    private static (Dictionary<string, object?>, object?) HandleCapture(JsonElement bindingJson)
    {
        BoundSource source = FindBinding(bindingJson);
        if (!EnsureCurrent(source, bindingJson, requireGeometry: true, out string error))
            return (Ok(("capture", (object)UnavailableCapture(source, error))), null);
        if (!IsInputDesktopUsable())
            return (Ok(("capture", (object)UnavailableCapture(source, "input desktop changed or is not WinSta0\\Default"))), null);
        long focusFence = Events.FocusEpoch;
        long inputEpochFence = GetLong(bindingJson, "input_domain_epoch");
        if (source.FollowForeground &&
            (focusFence != GetLong(bindingJson, "focus_epoch") ||
             Events.HumanState(source.Identity).Epoch != inputEpochFence))
            return (Ok(("capture", (object)UnavailableCapture(source,
                "foreground or physical-input epoch changed before capture"))), null);
        if (source.FollowForeground && !IsForegroundSource(source.Identity))
            return (Ok(("capture", (object)UnavailableCapture(source, "bound foreground source is not active"))), null);
        if (source.Identity.IsWindow && (IsIconic(source.Identity.Hwnd) || !IsWindowVisible(source.Identity.Hwnd)))
            return (Ok(("capture", (object)UnavailableCapture(source, IsIconic(source.Identity.Hwnd)
                ? "window is minimized; no fresh frame is assumed" : "window is not visible"))), null);
        if (IsProtectedCaptureWindow(source.Identity.Hwnd))
            return (Ok(("capture", (object)UnavailableCapture(source, "Windows reports capture exclusion/protection; no substitute image is returned"))), null);
        if (!CaptureSupported || D3DDevice is null)
            return (Ok(("capture", (object)UnavailableCapture(source, D3DCreateFailure ?? "Windows Graphics Capture or the hardware Direct3D 11 device is unavailable"))), null);
        try
        {
            CaptureResources resources = source.GetCaptureResources();
            resources.Start();
            if (!resources.FrameArrived.WaitOne(TimeSpan.FromMilliseconds(900)))
                return (Ok(("capture", (object)UnavailableCapture(source,
                    "no new Windows Graphics Capture frame arrived before the bounded deadline", "waiting_for_frame"))), null);
            resources.FrameArrived.Reset();
            byte[]? pixels = null;
            long sampleTicks = 0;
            int width = 0, height = 0;
            long receipt = MonotonicNs();
            for (int i = 0; i < 4; i++)
            {
                using Direct3D11CaptureFrame? frame = resources.Pool.TryGetNextFrame();
                if (frame is null)
                    break;
                SizeInt32 contentSize = frame.ContentSize;
                if (!ValidSize(contentSize.Width, contentSize.Height))
                {
                    source.CaptureUnavailable = $"WGC frame has unsupported content size {contentSize.Width}x{contentSize.Height}";
                    source.InvalidateGeometry(contentSize.Width, contentSize.Height);
                    source.DisposeCaptureResources();
                    return (Ok(("capture", (object)UnavailableCapture(source, source.CaptureUnavailable))), null);
                }
                if (contentSize.Width != source.Width || contentSize.Height != source.Height)
                {
                    source.InvalidateGeometry(contentSize.Width, contentSize.Height);
                    source.DisposeCaptureResources();
                    return (Ok(("capture", (object)UnavailableCapture(source, "WGC content geometry changed; rebind before using pixels or coordinates"))), null);
                }
                long ticks = frame.SystemRelativeTime.Ticks;
                if (ticks <= resources.LastSampleTicks)
                    continue;
                sampleTicks = ticks;
                width = contentSize.Width;
                height = contentSize.Height;
                pixels = CopySurfaceAsync(frame.Surface, width, height).GetAwaiter().GetResult();
                resources.LastSampleTicks = ticks;
                resources.Sequence++;
                source.CaptureSequence++;
                source.LastSampleNs = TimeSpanTicksToNs(ticks);
                receipt = MonotonicNs();
                break;
            }
            if (pixels is null)
                return (Ok(("capture", (object)UnavailableCapture(source,
                    "Windows Graphics Capture has not supplied a newer frame; stale pixels were not reused",
                    "waiting_for_frame"))), null);
            source.CaptureUnavailable = null;
            Dictionary<string, object?>? accessibility = CaptureAccessibility(source);
            if (source.FollowForeground &&
                (Events.FocusEpoch != focusFence || !IsForegroundSource(source.Identity) ||
                 Events.HumanState(source.Identity).Epoch != inputEpochFence))
                return (Ok(("capture", (object)UnavailableCapture(source,
                    "foreground or physical-input epoch changed during the bounded capture; the sample was discarded"))), null);
            var demonstration = Events.CaptureDemonstration(source, focusFence, inputEpochFence);
            List<Dictionary<string, object?>> events = Events.Since(source.Identity.Hwnd, source.Identity.IsWindow, source.LastEventSequence);
            if (events.Count > 0)
                source.LastEventSequence = Math.Max(source.LastEventSequence, events.Max(item => Convert.ToInt64(item["sequence"], CultureInfo.InvariantCulture)));
            var capture = new Dictionary<string, object?>
            {
                ["source_id"] = source.SourceId,
                ["source_instance"] = source.SourceInstance,
                ["source_epoch"] = source.SourceEpoch,
                ["environment_incarnation"] = EnvironmentIncarnation,
                ["geometry_revision"] = source.GeometryRevision,
                ["capture_state"] = "live",
                ["width"] = width,
                ["height"] = height,
                ["pixel_format"] = "BGRA8",
                ["color_space"] = "unknown SDR interpretation; no HDR claim",
                ["cursor_policy"] = "included by Windows.Graphics.Capture",
                ["sequence"] = source.CaptureSequence,
                ["sample_time_ns"] = TimeSpanTicksToNs(sampleTicks),
                ["sample_clock_domain"] = "windows-qpc",
                ["receipt_time_ns"] = receipt,
                ["receipt_clock_domain"] = "windows-qpc",
                ["coverage"] = new Dictionary<string, object?>
                {
                    ["complete"] = true, ["missing_regions"] = Array.Empty<object>(),
                    ["skipped_intervals"] = new[] { new { reason = "intermediate-capture-frames-not-retained" } },
                    ["unknown_regions"] = Array.Empty<object>(),
                    ["redacted_regions"] = Array.Empty<object>(),
                },
                ["accessibility"] = accessibility,
                ["accessibility_sample_time_ns"] = accessibility is null ? null : accessibility.GetValueOrDefault("sample_time_ns"),
                ["accessibility_provider"] = accessibility is null ? null : "Windows UI Automation",
                ["demonstration_events"] = demonstration.Events,
                ["demonstration_coverage"] = demonstration.Coverage,
                ["events"] = events,
                ["provenance"] = "Windows.Graphics.Capture",
            };
            return (Ok(("capture", (object)capture)), pixels);
        }
        catch (Exception ex)
        {
            source.CaptureUnavailable = $"Windows Graphics Capture failed: {SafeMessage(ex)}";
            source.DisposeCaptureResources();
            return (Ok(("capture", (object)UnavailableCapture(source, source.CaptureUnavailable))), null);
        }
    }

    private static Dictionary<string, object?> UnavailableCapture(BoundSource source, string reason, string state = "unavailable")
    {
        Dictionary<string, object?>? accessibility = CaptureAccessibility(source);
        if (accessibility is not null)
            source.CaptureSequence++;
        return new Dictionary<string, object?>
        {
            ["source_id"] = source.SourceId,
            ["source_instance"] = source.SourceInstance,
            ["source_epoch"] = source.SourceEpoch,
            ["environment_incarnation"] = EnvironmentIncarnation,
            ["geometry_revision"] = source.GeometryRevision,
            ["capture_state"] = source.Lost ? "lost" : state,
            ["reason"] = reason,
            ["width"] = source.Width,
            ["height"] = source.Height,
            ["pixel_format"] = "none",
            ["sequence"] = source.CaptureSequence,
            ["sample_time_ns"] = null,
            ["sample_clock_domain"] = null,
            ["receipt_time_ns"] = MonotonicNs(),
            ["receipt_clock_domain"] = "windows-qpc",
            ["coverage"] = new Dictionary<string, object?>
            {
                ["complete"] = false,
                ["missing_regions"] = new[] { Bounds(0, 0, source.Width, source.Height) },
                ["skipped_intervals"] = new[] { new { reason = "capture-unavailable; intermediate-frames-unknown" } },
                ["unknown_regions"] = Array.Empty<object>(),
                ["redacted_regions"] = Array.Empty<object>(),
            },
            ["accessibility"] = accessibility,
            ["accessibility_sample_time_ns"] = accessibility is null ? null : accessibility.GetValueOrDefault("sample_time_ns"),
            ["accessibility_provider"] = accessibility is null ? null : "Windows UI Automation",
            ["demonstration_events"] = new List<Dictionary<string, object?>>(),
            ["demonstration_coverage"] = Events.DemonstrationStatus(source, markMissing: true),
            ["events"] = Events.Since(source.Identity.Hwnd, source.Identity.IsWindow, source.LastEventSequence),
            ["provenance"] = "Windows.Graphics.Capture unavailable; no synthetic image substituted",
        };
    }

    private static Dictionary<string, object?> Dispatch(JsonElement bindingJson, JsonElement action)
    {
        BoundSource source = FindBinding(bindingJson);
        string? operation = GetString(action, "operation");
        JsonElement args = RequiredObject(action, "arguments");
        if (!EnsureCurrent(source, bindingJson, requireGeometry: true, out string error))
            return Rejected(error);
        List<Dictionary<string, object?>> pendingEvents = Events.Since(source.Identity.Hwnd, source.Identity.IsWindow, source.LastEventSequence);
        if (pendingEvents.Count > 0)
            source.LastEventSequence = Math.Max(source.LastEventSequence, pendingEvents.Max(item => Convert.ToInt64(item["sequence"], CultureInfo.InvariantCulture)));
        var humanState = Events.HumanState(source.Identity);
        bool effect = IsInputOperation(operation) || operation?.StartsWith("accessibility.", StringComparison.Ordinal) == true;
        long bindingInputEpoch = GetLong(bindingJson, "input_domain_epoch");
        long bindingFocusEpoch = GetLong(bindingJson, "focus_epoch");
        if (effect && bindingFocusEpoch != Events.FocusEpoch)
            return Rejected("foreground focus epoch changed after binding; refresh the live binding before dispatch");
        if (effect && (bindingInputEpoch != humanState.Epoch || humanState.Active))
        {
            Dictionary<string, object?> release = Neutralize(source, requireBinding: false);
            return new Dictionary<string, object?>
            {
                ["disposition"] = "rejected", ["delivered_count"] = 0,
                ["ack_strength"] = "none",
                ["detail"] = new Dictionary<string, object?>
                {
                    ["reason"] = bindingInputEpoch != humanState.Epoch
                        ? "input domain changed after this binding; request a fresh broker binding and lease"
                        : "non-injected input was observed recently; human control has priority",
                    ["binding_input_domain_epoch"] = bindingInputEpoch,
                    ["current_input_domain_epoch"] = humanState.Epoch,
                    ["human_control_active"] = humanState.Active,
                    ["events"] = pendingEvents,
                    ["neutralization"] = release,
                    ["automatic_replay"] = false,
                },
            };
        }
        if (effect && !IsInputDesktopUsable())
            return Rejected("the active input desktop is not WinSta0\\Default");
        if (operation is null)
            return Rejected("operation is missing");
        if (!effect)
            return Rejected("operation is unsupported by the Windows session helper");
        if (!Events.InputHooksAvailable)
            return Rejected("physical-input takeover hooks are unavailable; native control is disabled");
        if (!IsForegroundTarget(source))
            return Rejected("target is not the foreground window on the active input desktop; helper never redirects input to the current foreground app");
        if (source.Identity.IsWindow && (IsIconic(source.Identity.Hwnd) || !IsWindowVisible(source.Identity.Hwnd)))
            return Rejected("target window is minimized or not visible");
        if (operation.StartsWith("accessibility.", StringComparison.Ordinal))
            return DispatchAccessibility(source, operation, args, pendingEvents, bindingFocusEpoch, bindingInputEpoch);
        try
        {
            INPUT[] inputs = MakeInputs(source, operation, args);
            var currentHuman = Events.HumanState(source.Identity);
            if (Events.FocusEpoch != bindingFocusEpoch || currentHuman.Epoch != bindingInputEpoch ||
                currentHuman.Active || !IsForegroundTarget(source) || !IsInputDesktopUsable())
                return Rejected("focus, input desktop, or human control changed before native input delivery; rebind");
            if (inputs.Length == 0 || inputs.Length > MaxInputEvents)
                return Rejected($"input batch must contain 1..{MaxInputEvents} native events");
            uint inserted = SendInput((uint)inputs.Length, inputs, Marshal.SizeOf<INPUT>());
            UpdateOwnedControls(source, operation, args, inputs, inserted);
            string disposition = inserted == 0 ? "not-started" : inserted == inputs.Length ? "delivered" : "partially-delivered";
            return new Dictionary<string, object?>
            {
                ["disposition"] = disposition,
                ["delivered_count"] = inserted,
                ["ack_strength"] = "SendInput insertion count only",
                ["detail"] = new Dictionary<string, object?>
                {
                    ["requested_count"] = inputs.Length,
                    ["inserted_count"] = inserted,
                    ["input_desktop"] = CurrentInputDesktop(),
                    ["foreground_window"] = WindowId(GetForegroundWindow()),
                    ["target_focus_verified"] = true,
                    ["observed_application_result"] = "not observed",
                    ["physical_state_distinguished"] = false,
                    ["events"] = pendingEvents,
                    ["last_error"] = inserted == 0 ? Marshal.GetLastWin32Error() : 0,
                },
            };
        }
        catch (ArgumentException ex)
        {
            return Rejected(ex.Message);
        }
        catch (Exception ex)
        {
            return new Dictionary<string, object?>
            {
                ["disposition"] = "not-started", ["delivered_count"] = 0,
                ["ack_strength"] = "none", ["detail"] = SafeMessage(ex),
            };
        }
    }

    private static Dictionary<string, object?> DispatchAccessibility(BoundSource source, string operation, JsonElement args,
        List<Dictionary<string, object?>> pendingEvents, long bindingFocusEpoch, long bindingInputEpoch)
    {
        if (!source.Identity.IsWindow)
            return Rejected("UI Automation is available only for a bound window source");
        if (source.UiaTimedOut)
            return Rejected("UI Automation was disabled for this source after a provider timeout");
        if (!AccessibilityLive(source))
            return Rejected("UI Automation is not live for this source");
        if (!args.TryGetProperty("node_ref", out JsonElement nodeValue) || nodeValue.ValueKind != JsonValueKind.String)
            return Rejected("accessibility operation requires a current node_ref from the latest structured snapshot");
        string nodeRef = nodeValue.GetString()!;
        if (!source.NodeRuntimeIds.TryGetValue(nodeRef, out int[]? runtimeId))
            return Rejected("UI Automation node reference is stale or was not present in the latest snapshot");
        IntPtr sourceHwnd = source.Identity.Hwnd;
        int sourceProcessId = source.Identity.ProcessId;
        var outcome = RunUiaBounded(() =>
        {
            AutomationElement root = AutomationElement.FromHandle(sourceHwnd);
            if (root.Current.ProcessId != sourceProcessId)
                return "source_stale";
            AutomationElement? target = FindByRuntimeId(root, runtimeId);
            if (target is null)
                return "stale";
            var currentHuman = Events.HumanState(source.Identity);
            if (Events.FocusEpoch != bindingFocusEpoch || currentHuman.Epoch != bindingInputEpoch ||
                currentHuman.Active || !IsForegroundTarget(source) || !IsInputDesktopUsable())
                return "interrupted";
            switch (operation)
            {
                case "accessibility.invoke":
                    ((InvokePattern)target.GetCurrentPattern(InvokePattern.Pattern)).Invoke();
                    break;
                case "accessibility.set_value":
                    if (!args.TryGetProperty("value", out JsonElement value) || value.ValueKind != JsonValueKind.String)
                        throw new ArgumentException("set_value requires a string value");
                    string text = value.GetString()!;
                    if (Encoding.UTF8.GetByteCount(text) > 4096)
                        throw new ArgumentException("UI Automation value exceeds 4096 UTF-8 bytes");
                    if (target.Current.IsPassword)
                        throw new ArgumentException("password controls are not writable through this helper");
                    var valuePattern = (ValuePattern)target.GetCurrentPattern(ValuePattern.Pattern);
                    if (valuePattern.Current.IsReadOnly)
                        throw new ArgumentException("UI Automation provider reports a read-only value");
                    valuePattern.SetValue(text);
                    break;
                case "accessibility.select":
                    ((SelectionItemPattern)target.GetCurrentPattern(SelectionItemPattern.Pattern)).Select();
                    break;
                case "accessibility.toggle":
                    string toggle = RequiredString(args, "state");
                    var togglePattern = (TogglePattern)target.GetCurrentPattern(TogglePattern.Pattern);
                    ToggleState wanted = toggle switch
                    {
                        "on" => ToggleState.On,
                        "off" => ToggleState.Off,
                        "indeterminate" => ToggleState.Indeterminate,
                        _ => throw new ArgumentException("toggle state must be on, off, or indeterminate"),
                    };
                    if (togglePattern.Current.ToggleState != wanted)
                        togglePattern.Toggle();
                    break;
                case "accessibility.expand":
                    string expand = RequiredString(args, "state");
                    var expandPattern = (ExpandCollapsePattern)target.GetCurrentPattern(ExpandCollapsePattern.Pattern);
                    if (expand == "expanded" && expandPattern.Current.ExpandCollapseState != ExpandCollapseState.Expanded)
                        expandPattern.Expand();
                    else if (expand == "collapsed" && expandPattern.Current.ExpandCollapseState != ExpandCollapseState.Collapsed)
                        expandPattern.Collapse();
                    else if (expand is not ("expanded" or "collapsed"))
                        throw new ArgumentException("expand state must be expanded or collapsed");
                    break;
                case "accessibility.focus":
                    target.SetFocus();
                    break;
                default:
                    throw new ArgumentException("UI Automation operation is unsupported");
            }
            return "provider_call_returned";
        }, 600);
        if (outcome.TimedOut)
        {
            source.UiaTimedOut = true;
            source.UiaAvailable = false;
            source.NodeRuntimeIds.Clear();
            return new Dictionary<string, object?>
            {
                ["disposition"] = "unknown", ["delivered_count"] = 0,
                ["ack_strength"] = "none",
                ["detail"] = new Dictionary<string, object?>
                {
                    ["reason"] = "UI Automation provider exceeded 600 ms; call may still be in progress",
                    ["external_effect_may_have_started"] = true,
                    ["automatic_replay"] = false,
                    ["events"] = pendingEvents,
                },
            };
        }
        if (outcome.Error is not null)
        {
            source.UiaAvailable = false;
            source.NodeRuntimeIds.Clear();
            return Rejected($"UI Automation failed: {outcome.Error}");
        }
        if (outcome.Value == "source_stale")
        {
            source.MarkLost("UI Automation root no longer matches the bound window process");
            return Rejected("bound window changed during UI Automation action");
        }
        if (outcome.Value == "stale")
            return Rejected("UI Automation object became stale; re-capture and bind a current node before acting");
        if (outcome.Value == "interrupted")
            return Rejected("focus, input desktop, or human control changed before UI Automation input delivery; rebind");
        if (!IdentityStillCurrent(source.Identity, out string sourceReason))
        {
            source.MarkLost($"UI Automation source changed during action: {sourceReason}");
            return new Dictionary<string, object?>
            {
                ["disposition"] = "unknown", ["delivered_count"] = 0, ["ack_strength"] = "none",
                ["detail"] = new Dictionary<string, object?>
                {
                    ["reason"] = "bound window changed during UI Automation action",
                    ["external_effect_may_have_started"] = true, ["automatic_replay"] = false,
                },
            };
        }
        return new Dictionary<string, object?>
        {
            ["disposition"] = "delivered", ["delivered_count"] = 1,
            ["ack_strength"] = "provider_call_returned",
            ["detail"] = new Dictionary<string, object?>
            {
                ["provider"] = "Windows UI Automation",
                ["provider_call_returned"] = true,
                ["observed_application_result"] = "not observed",
                ["node_ref"] = nodeRef,
                ["events"] = pendingEvents,
            },
        };
    }

    private static Dictionary<string, object?> RevalidateBinding(JsonElement bindingJson)
    {
        BoundSource source;
        try { source = FindBinding(bindingJson); }
        catch (Exception ex)
        {
            return new Dictionary<string, object?> { ["supported"] = true, ["valid"] = false, ["reason"] = SafeMessage(ex) };
        }
        if (!EnsureCurrent(source, bindingJson, requireGeometry: false, out string reason))
            return new Dictionary<string, object?> { ["supported"] = true, ["valid"] = false, ["reason"] = reason };
        Dictionary<string, object?> current = BindingDescription(source);
        current["supported"] = true;
        current["valid"] = true;
        return current;
    }

    private static Dictionary<string, object?> RevalidateTarget(JsonElement bindingJson, JsonElement semanticTarget)
    {
        BoundSource source;
        try { source = FindBinding(bindingJson); }
        catch (Exception ex) { return TargetInvalid(SafeMessage(ex)); }
        if (!EnsureCurrent(source, bindingJson, requireGeometry: true, out string reason))
            return TargetInvalid(reason);
        if (!IsInputDesktopUsable())
            return TargetInvalid("the active input desktop is not WinSta0\\Default");
        if (!source.Identity.IsWindow)
            return TargetInvalid("Windows UI Automation target validation requires a bound window");
        if (IsIconic(source.Identity.Hwnd) || !IsWindowVisible(source.Identity.Hwnd))
            return TargetInvalid("bound window is minimized or not visible");
        if (source.UiaTimedOut)
            return TargetInvalid("UI Automation was disabled for this source after a provider timeout");
        if (!AccessibilityLive(source))
            return TargetInvalid("UI Automation provider is not live for this source");
        if (!string.Equals(GetString(semanticTarget, "provider"), "Windows UI Automation", StringComparison.Ordinal))
            return TargetInvalid("Windows backend cannot revalidate this semantic-target provider", supported: false);
        if (!semanticTarget.TryGetProperty("runtime_id", out JsonElement value) ||
            value.ValueKind != JsonValueKind.Array || value.GetArrayLength() is < 1 or > 32)
            return TargetInvalid("semantic target requires a nonempty bounded UI Automation runtime_id array");
        int[] runtimeId = new int[value.GetArrayLength()];
        int index = 0;
        foreach (JsonElement item in value.EnumerateArray())
        {
            if (item.ValueKind != JsonValueKind.Number || !item.TryGetInt32(out runtimeId[index]))
                return TargetInvalid("UI Automation runtime_id components must be signed 32-bit integers");
            index++;
        }
        bool observed;
        lock (source.NodeLock)
            observed = source.NodeRuntimeIds.Values.Any(candidate => candidate.SequenceEqual(runtimeId));
        if (!observed)
            return TargetInvalid("UI Automation runtime_id was not present in the most recent snapshot for this source");
        IntPtr sourceHwnd = source.Identity.Hwnd;
        int sourceProcessId = source.Identity.ProcessId;
        long focusFence = Events.FocusEpoch;
        var outcome = RunUiaBounded(() =>
        {
            if (source.FollowForeground &&
                (Events.FocusEpoch != focusFence || !IsForegroundSource(source.Identity)))
                return "focus_changed";
            AutomationElement root = AutomationElement.FromHandle(sourceHwnd);
            if (root.Current.ProcessId != sourceProcessId)
                return "source_stale";
            string result = FindByRuntimeId(root, runtimeId) is null ? "stale" : "found";
            return source.FollowForeground &&
                (Events.FocusEpoch != focusFence || !IsForegroundSource(source.Identity))
                    ? "focus_changed" : result;
        }, 600);
        if (outcome.TimedOut)
        {
            source.UiaTimedOut = true;
            source.UiaAvailable = false;
            lock (source.NodeLock) source.NodeRuntimeIds.Clear();
            return TargetInvalid("UI Automation provider exceeded 600 ms; no target was assumed live");
        }
        if (outcome.Error is not null)
        {
            source.UiaAvailable = false;
            lock (source.NodeLock) source.NodeRuntimeIds.Clear();
            return TargetInvalid($"UI Automation target validation failed: {outcome.Error}");
        }
        if (outcome.Value == "focus_changed" || source.FollowForeground &&
            (Events.FocusEpoch != focusFence || !IsForegroundSource(source.Identity)))
            return TargetInvalid("foreground changed during UI Automation target validation");
        if (outcome.Value == "source_stale")
        {
            source.UiaAvailable = false;
            lock (source.NodeLock) source.NodeRuntimeIds.Clear();
            source.MarkLost("UI Automation root no longer matches the bound window process");
            return TargetInvalid("UI Automation root no longer matches the bound window process");
        }
        if (!IdentityStillCurrent(source.Identity, out string sourceReason))
        {
            source.MarkLost($"UI Automation source changed during target validation: {sourceReason}");
            return TargetInvalid($"bound window changed during UI Automation target validation: {sourceReason}");
        }
        bool valid = outcome.Value == "found";
        return new Dictionary<string, object?>
        {
            ["supported"] = true,
            ["valid"] = valid,
            ["provider"] = "Windows UI Automation",
            ["detail"] = valid ? "runtime_id is present in the live bound-window tree" : "runtime_id is no longer present in the live bound-window tree",
        };
    }

    private static Dictionary<string, object?> TargetInvalid(string reason, bool supported = true) =>
        new() { ["supported"] = supported, ["valid"] = false, ["detail"] = reason };

    private static Dictionary<string, object?> Neutralize(BoundSource source, bool requireBinding)
    {
        if (requireBinding && source.Lost && (source.OwnedKeys.Count != 0 || source.OwnedButtons.Count != 0))
            return new Dictionary<string, object?> { ["confirmed"] = false, ["detail"] = source.LossReason };
        if (SessionId == 0 || !IsInputDesktopUsable())
            return new Dictionary<string, object?>
            {
                ["confirmed"] = false,
                ["detail"] = new Dictionary<string, object?>
                {
                    ["reason"] = "input desktop or session is unavailable; synthetic releases were not sent",
                    ["remaining_keys"] = source.OwnedKeys.ToArray(),
                    ["remaining_buttons"] = source.OwnedButtons.ToArray(),
                },
            };
        var releases = new List<INPUT>();
        var labels = new List<(bool key, string name)>();
        foreach (int vk in source.OwnedKeys.OrderBy(value => value))
        {
            releases.Add(KeyInput((ushort)vk, keyUp: true));
            labels.Add((true, vk.ToString(CultureInfo.InvariantCulture)));
        }
        foreach (string button in source.OwnedButtons.OrderBy(value => value, StringComparer.Ordinal))
        {
            releases.Add(ButtonInput(button, down: false));
            labels.Add((false, button));
        }
        if (releases.Count == 0)
            return new Dictionary<string, object?> { ["confirmed"] = true, ["detail"] = "no synthetic controls are known to be held by this helper" };
        uint inserted = SendInput((uint)releases.Count, releases.ToArray(), Marshal.SizeOf<INPUT>());
        for (int i = 0; i < Math.Min((int)inserted, labels.Count); i++)
        {
            if (labels[i].key && int.TryParse(labels[i].name, out int vk))
                source.OwnedKeys.Remove(vk);
            else if (!labels[i].key)
                source.OwnedButtons.Remove(labels[i].name);
        }
        bool confirmed = inserted == releases.Count && source.OwnedKeys.Count == 0 && source.OwnedButtons.Count == 0;
        return new Dictionary<string, object?>
        {
            ["confirmed"] = confirmed,
            ["detail"] = new Dictionary<string, object?>
            {
                ["requested_release_count"] = releases.Count,
                ["inserted_release_count"] = inserted,
                ["remaining_keys"] = source.OwnedKeys.ToArray(),
                ["remaining_buttons"] = source.OwnedButtons.ToArray(),
                ["physical_key_state_distinguished"] = false,
                ["observed_application_result"] = "not observed",
                ["last_error"] = inserted == 0 ? Marshal.GetLastWin32Error() : 0,
            },
        };
    }

    private static INPUT[] MakeInputs(BoundSource source, string operation, JsonElement args)
    {
        switch (operation)
        {
            case "keyboard.key":
            {
                string state = RequiredString(args, "state");
                if (state is not ("down" or "up"))
                    throw new ArgumentException("key state must be down or up");
                int vk = ResolveVirtualKey(args);
                return new[] { KeyInput((ushort)vk, keyUp: state == "up") };
            }
            case "keyboard.text":
            {
                string text = RequiredString(args, "text");
                if (Encoding.UTF8.GetByteCount(text) > 1024)
                    throw new ArgumentException("text input exceeds 1024 UTF-8 bytes");
                char[] units = text.ToCharArray();
                if (units.Length == 0 || units.Length > MaxInputEvents / 2)
                    throw new ArgumentException($"text input must contain 1..{MaxInputEvents / 2} UTF-16 code units");
                var result = new INPUT[units.Length * 2];
                for (int i = 0; i < units.Length; i++)
                {
                    result[i * 2] = UnicodeInput(units[i], keyUp: false);
                    result[i * 2 + 1] = UnicodeInput(units[i], keyUp: true);
                }
                return result;
            }
            case "pointer.absolute":
            {
                if (!DpiPhysical)
                    throw new ArgumentException("absolute pointer input is unavailable without verified physical-pixel DPI awareness");
                int x = RequiredInt(args, "x", 0, source.Width - 1);
                int y = RequiredInt(args, "y", 0, source.Height - 1);
                int screenX = checked(source.Identity.Left + (int)Math.Round((double)x * source.Identity.Width / source.Width, MidpointRounding.AwayFromZero));
                int screenY = checked(source.Identity.Top + (int)Math.Round((double)y * source.Identity.Height / source.Height, MidpointRounding.AwayFromZero));
                if (!GetVirtualScreen(out int left, out int top, out int width, out int height))
                    throw new ArgumentException("virtual-screen geometry is unavailable");
                int dx = width <= 1 ? 0 : (int)Math.Round((double)(screenX - left) * 65535 / (width - 1), MidpointRounding.AwayFromZero);
                int dy = height <= 1 ? 0 : (int)Math.Round((double)(screenY - top) * 65535 / (height - 1), MidpointRounding.AwayFromZero);
                if (dx is < 0 or > 65535 || dy is < 0 or > 65535)
                    throw new ArgumentException("source coordinate falls outside the virtual desktop");
                return new[] { MouseInput(dx, dy, 0, MOUSEEVENTF_MOVE | MOUSEEVENTF_ABSOLUTE | MOUSEEVENTF_VIRTUALDESK) };
            }
            case "pointer.relative":
            {
                int dx = RequiredInt(args, "dx", -MaxSide, MaxSide);
                int dy = RequiredInt(args, "dy", -MaxSide, MaxSide);
                return new[] { MouseInput(dx, dy, 0, MOUSEEVENTF_MOVE) };
            }
            case "pointer.button":
            {
                string button = RequiredString(args, "button");
                string state = RequiredString(args, "state");
                if (state is not ("down" or "up"))
                    throw new ArgumentException("button state must be down or up");
                return new[] { ButtonInput(button, down: state == "down") };
            }
            case "pointer.wheel":
            {
                int dx = RequiredInt(args, "dx", -1200, 1200);
                int dy = RequiredInt(args, "dy", -1200, 1200);
                if (dx == 0 && dy == 0)
                    throw new ArgumentException("wheel delta cannot be zero in both axes");
                var result = new List<INPUT>(2);
                if (dy != 0)
                    result.Add(MouseInput(0, 0, unchecked((uint)dy), MOUSEEVENTF_WHEEL));
                if (dx != 0)
                    result.Add(MouseInput(0, 0, unchecked((uint)dx), MOUSEEVENTF_HWHEEL));
                return result.ToArray();
            }
            default:
                throw new ArgumentException("input operation is unsupported");
        }
    }

    private static void UpdateOwnedControls(BoundSource source, string operation, JsonElement args, INPUT[] inputs, uint inserted)
    {
        if (inserted == 0)
            return;
        if (operation == "keyboard.key")
        {
            int vk = ResolveVirtualKey(args);
            if (GetString(args, "state") == "down")
                source.OwnedKeys.Add(vk);
            else
                source.OwnedKeys.Remove(vk);
        }
        else if (operation == "pointer.button")
        {
            string button = RequiredString(args, "button");
            if (GetString(args, "state") == "down")
                source.OwnedButtons.Add(button);
            else
                source.OwnedButtons.Remove(button);
        }
        if (inserted < inputs.Length)
            source.AddEvent("partial_input", new Dictionary<string, object?>
            {
                ["inserted_count"] = inserted, ["requested_count"] = inputs.Length,
                ["result"] = "remaining input events were not replayed",
            });
    }

    private static int ResolveVirtualKey(JsonElement args)
    {
        if (args.TryGetProperty("vk", out JsonElement vkValue) && vkValue.TryGetInt32(out int vk))
        {
            if (vk is < 1 or > 255 || vk is 3 or 0x5B or 0x5C and not (0x5B or 0x5C))
                throw new ArgumentException("virtual-key code must be a supported non-reserved value in 1..255");
            return vk;
        }
        string key = RequiredString(args, "key");
        if (key.Length == 1)
        {
            char ch = char.ToUpperInvariant(key[0]);
            if (ch is >= 'A' and <= 'Z' or >= '0' and <= '9')
                return ch;
        }
        if (key.Length >= 2 && (key[0] is 'F' or 'f') && int.TryParse(key.AsSpan(1), out int functionKey) && functionKey is >= 1 and <= 24)
            return 0x70 + functionKey - 1;
        return key.ToLowerInvariant() switch
        {
            "backspace" => 0x08, "tab" => 0x09, "enter" => 0x0D, "shift" => 0x10,
            "ctrl" or "control" => 0x11, "alt" => 0x12, "pause" => 0x13,
            "capslock" => 0x14, "escape" or "esc" => 0x1B, "space" => 0x20,
            "pageup" => 0x21, "pagedown" => 0x22, "end" => 0x23, "home" => 0x24,
            "left" => 0x25, "up" => 0x26, "right" => 0x27, "down" => 0x28,
            "printscreen" => 0x2C, "insert" => 0x2D, "delete" => 0x2E,
            "lshift" => 0xA0, "rshift" => 0xA1, "lctrl" => 0xA2, "rctrl" => 0xA3,
            "lalt" => 0xA4, "ralt" => 0xA5, "numlock" => 0x90, "scrolllock" => 0x91,
            "numpad0" => 0x60, "numpad1" => 0x61, "numpad2" => 0x62, "numpad3" => 0x63,
            "numpad4" => 0x64, "numpad5" => 0x65, "numpad6" => 0x66, "numpad7" => 0x67,
            "numpad8" => 0x68, "numpad9" => 0x69, "multiply" => 0x6A, "add" => 0x6B,
            "subtract" => 0x6D, "decimal" => 0x6E, "divide" => 0x6F,
            "lwin" or "left_windows" => 0x5B, "rwin" or "right_windows" => 0x5C,
            _ => throw new ArgumentException("key must be a supported key name or Windows virtual-key code"),
        };
    }

    private static Dictionary<string, object?> AccessibilitySnapshot(BoundSource source)
    {
        if (source.UiaTimedOut)
        {
            source.UiaAvailable = false;
            return new Dictionary<string, object?>
            {
                ["status"] = "unavailable", ["reason"] = "a previous UI Automation provider call timed out; this source's UIA calls are disabled",
                ["provider"] = "Windows UI Automation", ["nodes"] = Array.Empty<object>(),
                ["truncated"] = false, ["sample_time_ns"] = MonotonicNs(),
            };
        }
        long focusFence = Events.FocusEpoch;
        if (!AccessibilityLive(source))
        {
            source.UiaAvailable = false;
            lock (source.NodeLock) source.NodeRuntimeIds.Clear();
            return new Dictionary<string, object?>
            {
                ["status"] = "unavailable", ["reason"] = "UI Automation is not live for this bound source",
                ["provider"] = "Windows UI Automation", ["nodes"] = Array.Empty<object>(),
                ["truncated"] = false, ["sample_time_ns"] = MonotonicNs(),
            };
        }
        var outcome = RunUiaBounded(() =>
        {
            if (source.FollowForeground &&
                (Events.FocusEpoch != focusFence || !IsForegroundSource(source.Identity)))
                return null;
            return BuildAccessibilityTree(source);
        }, 600);
        if (outcome.TimedOut)
        {
            source.UiaTimedOut = true;
            source.UiaAvailable = false;
            lock (source.NodeLock) source.NodeRuntimeIds.Clear();
            return new Dictionary<string, object?>
            {
                ["status"] = "timed_out", ["reason"] = "Windows UI Automation provider exceeded 600 ms; no previous tree is reused",
                ["provider"] = "Windows UI Automation", ["nodes"] = Array.Empty<object>(),
                ["truncated"] = false, ["sample_time_ns"] = MonotonicNs(),
            };
        }
        if (source.FollowForeground &&
            (Events.FocusEpoch != focusFence || !IsForegroundSource(source.Identity)))
        {
            source.UiaAvailable = false;
            lock (source.NodeLock) source.NodeRuntimeIds.Clear();
            return new Dictionary<string, object?>
            {
                ["status"] = "unavailable", ["reason"] = "foreground changed during UI Automation; no snapshot was returned",
                ["provider"] = "Windows UI Automation", ["nodes"] = Array.Empty<object>(),
                ["truncated"] = false, ["sample_time_ns"] = MonotonicNs(),
            };
        }
        if (outcome.Error is not null || outcome.Value is null)
        {
            source.UiaAvailable = false;
            lock (source.NodeLock) source.NodeRuntimeIds.Clear();
            return new Dictionary<string, object?>
            {
                ["status"] = "unavailable",
                ["reason"] = outcome.Error ?? "Windows UI Automation produced no snapshot",
                ["provider"] = "Windows UI Automation", ["nodes"] = Array.Empty<object>(),
                ["truncated"] = false, ["sample_time_ns"] = MonotonicNs(),
            };
        }
        if (!IdentityStillCurrent(source.Identity, out string sourceReason))
        {
            source.MarkLost($"UI Automation source changed during capture: {sourceReason}");
            return new Dictionary<string, object?>
            {
                ["status"] = "unavailable", ["reason"] = source.LossReason,
                ["provider"] = "Windows UI Automation", ["nodes"] = Array.Empty<object>(),
                ["truncated"] = false, ["sample_time_ns"] = MonotonicNs(),
            };
        }
        source.UiaAvailable = true;
        return outcome.Value;
    }

    private static Dictionary<string, object?> BuildAccessibilityTree(BoundSource source)
    {
        var nodes = new List<Dictionary<string, object?>>();
        var nodeMap = new Dictionary<string, int[]>(StringComparer.Ordinal);
        var pending = new Queue<(AutomationElement element, int depth)>();
        AutomationElement root = AutomationElement.FromHandle(source.Identity.Hwnd);
        if (root.Current.ProcessId != source.Identity.ProcessId)
            throw new InvalidOperationException("UI Automation root no longer matches the bound window process");
        pending.Enqueue((root, 0));
        var walker = TreeWalker.RawViewWalker;
        bool truncated = false;
        bool textSpansRead = false;
        int textBudget = MaxTreeTextChars;
        while (pending.Count > 0 && nodes.Count < MaxTreeNodes)
        {
            (AutomationElement element, int depth) = pending.Dequeue();
            try
            {
                var info = element.Current;
                int[]? runtimeId = element.GetRuntimeId();
                if (runtimeId is null || runtimeId.Length == 0)
                    continue;
                string nodeRef = Guid.NewGuid().ToString("N");
                nodeMap[nodeRef] = runtimeId;
                bool password = info.IsPassword;
                string? name = null;
                if (!password && info.ControlType != ControlType.Edit && info.ControlType != ControlType.Document)
                {
                    try { name = string.IsNullOrWhiteSpace(info.Name) ? null : Bounded(info.Name, 240); }
                    catch { }
                }
                var patterns = new List<string>();
                AddPattern(element, InvokePattern.Pattern, "invoke", patterns);
                AddPattern(element, ValuePattern.Pattern, "value", patterns);
                AddPattern(element, SelectionItemPattern.Pattern, "selection_item", patterns);
                AddPattern(element, TogglePattern.Pattern, "toggle", patterns);
                AddPattern(element, ExpandCollapsePattern.Pattern, "expand_collapse", patterns);
                string? text = null;
                bool textTruncated = false;
                if (!password && textBudget > 0 &&
                    (info.ControlType == ControlType.Edit || info.ControlType == ControlType.Document))
                {
                    try
                    {
                        if (element.TryGetCurrentPattern(TextPattern.Pattern, out object? pattern) && pattern is TextPattern textPattern)
                        {
                            int limit = Math.Min(MaxNodeTextChars, textBudget);
                            string sampled = textPattern.DocumentRange.GetText(limit + 1);
                            int length = Math.Min(limit, sampled.Length);
                            if (length > 0 && char.IsHighSurrogate(sampled[length - 1]))
                                length--;
                            textTruncated = sampled.Length > length;
                            text = sampled[..length].Replace('\0', ' ');
                            textBudget -= length;
                            textSpansRead = true;
                        }
                    }
                    catch (COMException) { }
                    catch (ElementNotAvailableException) { }
                    catch (InvalidOperationException) { }
                }
                var bounds = info.BoundingRectangle;
                nodes.Add(new Dictionary<string, object?>
                {
                    ["node_ref"] = nodeRef,
                    ["runtime_id"] = runtimeId,
                    ["name"] = name,
                    ["automation_id"] = Bounded(info.AutomationId, 128),
                    ["control_type"] = info.ControlType.ProgrammaticName,
                    ["class_name"] = Bounded(info.ClassName, 128),
                    ["enabled"] = info.IsEnabled,
                    ["offscreen"] = info.IsOffscreen,
                    ["password"] = password,
                    ["bounds"] = RectBounds(bounds),
                    ["patterns"] = patterns,
                    ["text"] = text,
                    ["text_truncated"] = textTruncated,
                });
                if (depth < MaxTreeDepth)
                {
                    AutomationElement? child = walker.GetFirstChild(element);
                    int childCount = 0;
                    while (child is not null && childCount < MaxTreeNodes)
                    {
                        pending.Enqueue((child, depth + 1));
                        childCount++;
                        child = walker.GetNextSibling(child);
                    }
                }
                else if (walker.GetFirstChild(element) is not null)
                {
                    truncated = true;
                }
            }
            catch (ElementNotAvailableException) { }
            catch (COMException) { }
        }
        if (pending.Count > 0)
            truncated = true;
        lock (source.NodeLock)
        {
            source.NodeRuntimeIds = nodeMap;
        }
        return new Dictionary<string, object?>
        {
            ["status"] = "available",
            ["provider"] = "Windows UI Automation",
            ["source_id"] = source.SourceId,
            ["source_instance"] = source.SourceInstance,
            ["geometry_revision"] = source.GeometryRevision,
            ["sample_time_ns"] = MonotonicNs(),
            ["nodes"] = nodes,
            ["truncated"] = truncated,
            ["values_read"] = false,
            ["text_spans_read"] = textSpansRead,
        };
    }

    private static void AddPattern(AutomationElement element, AutomationPattern pattern, string name, List<string> patterns)
    {
        try
        {
            if (element.TryGetCurrentPattern(pattern, out _))
                patterns.Add(name);
        }
        catch { }
    }

    private static AutomationElement? FindByRuntimeId(IntPtr hwnd, int[] expected) =>
        FindByRuntimeId(AutomationElement.FromHandle(hwnd), expected);

    private static AutomationElement? FindByRuntimeId(AutomationElement root, int[] expected)
    {
        var pending = new Queue<(AutomationElement element, int depth)>();
        pending.Enqueue((root, 0));
        var walker = TreeWalker.RawViewWalker;
        int visited = 0;
        while (pending.Count > 0 && visited < 4096)
        {
            (AutomationElement element, int depth) = pending.Dequeue();
            visited++;
            try
            {
                int[]? actual = element.GetRuntimeId();
                if (actual is not null && actual.SequenceEqual(expected))
                    return element;
                if (depth >= MaxTreeDepth)
                    continue;
                AutomationElement? child = walker.GetFirstChild(element);
                while (child is not null && pending.Count < 4096)
                {
                    pending.Enqueue((child, depth + 1));
                    child = walker.GetNextSibling(child);
                }
            }
            catch (ElementNotAvailableException) { }
            catch (COMException) { }
        }
        return null;
    }

    private static (T? Value, string? Error, bool TimedOut) RunUiaBounded<T>(Func<T> action, int timeoutMs)
    {
        T? value = default;
        string? error = null;
        var finished = new TaskCompletionSource<bool>(TaskCreationOptions.RunContinuationsAsynchronously);
        var thread = new Thread(() =>
        {
            try { value = action(); }
            catch (Exception ex) { error = SafeMessage(ex); }
            finally { finished.TrySetResult(true); }
        }) { IsBackground = true, Name = "Cassi Windows UI Automation call" };
        thread.SetApartmentState(ApartmentState.STA);
        thread.Start();
        if (!finished.Task.Wait(TimeSpan.FromMilliseconds(timeoutMs)))
            return (default, null, true);
        return (value, error, false);
    }

    private static async Task<byte[]> CopySurfaceAsync(Windows.Graphics.DirectX.Direct3D11.IDirect3DSurface surface, int width, int height)
    {
        using SoftwareBitmap bitmap = await SoftwareBitmap.CreateCopyFromSurfaceAsync(
            surface, BitmapAlphaMode.Ignore).AsTask().ConfigureAwait(false);
        if (bitmap.PixelWidth != width || bitmap.PixelHeight != height || bitmap.BitmapPixelFormat != BitmapPixelFormat.Bgra8)
            throw new InvalidOperationException("WGC surface conversion did not preserve reported BGRA8 dimensions");
        using BitmapBuffer buffer = bitmap.LockBuffer(BitmapBufferAccessMode.Read);
        BitmapPlaneDescription plane = buffer.GetPlaneDescription(0);
        int rowBytes = checked(width * 4);
        if (plane.Width != width || plane.Height != height || plane.Stride < rowBytes || plane.StartIndex < 0)
            throw new InvalidOperationException("WGC bitmap plane has unsupported dimensions or stride");
        using IMemoryBufferReference reference = buffer.CreateReference();
        var memory = reference.As<IMemoryBufferByteAccess>();
        unsafe
        {
            memory.GetBuffer(out byte* source, out uint capacity);
            long required = (long)plane.StartIndex + (long)(height - 1) * plane.Stride + rowBytes;
            if (required > capacity)
                throw new InvalidOperationException("WGC bitmap plane exceeds its mapped buffer");
            byte[] output = new byte[checked(rowBytes * height)];
            fixed (byte* destination = output)
            {
                for (int y = 0; y < height; y++)
                    Buffer.MemoryCopy(source + plane.StartIndex + y * plane.Stride, destination + y * rowBytes, rowBytes, rowBytes);
            }
            return output;
        }
    }

    private static bool EnsureCurrent(BoundSource source, JsonElement binding, bool requireGeometry, out string error)
    {
        error = "";
        if (source.Lost)
        {
            error = source.LossReason ?? "source is lost";
            return false;
        }
        if (SessionId == 0 || (source.Identity.IsWindow && GetSessionId(source.Identity.ProcessId, source.Identity.Hwnd) != SessionId))
        {
            source.MarkLost("source session changed or is no longer the helper's interactive session");
            error = source.LossReason!;
            return false;
        }
        if (!IdentityStillCurrent(source.Identity, out string identityReason))
        {
            source.MarkLost(identityReason);
            error = identityReason;
            return false;
        }
        UpdateGeometry(source);
        if (!string.Equals(GetString(binding, "source_id"), source.SourceId, StringComparison.Ordinal) ||
            !string.Equals(GetString(binding, "source_instance"), source.SourceInstance, StringComparison.Ordinal) ||
            !string.Equals(GetString(binding, "environment_incarnation"), EnvironmentIncarnation, StringComparison.Ordinal) ||
            GetLong(binding, "source_epoch") != source.SourceEpoch)
        {
            error = "source instance, epoch, or environment incarnation changed";
            return false;
        }
        if (requireGeometry && GetLong(binding, "geometry_revision") != source.GeometryRevision)
        {
            error = "source geometry changed; rebind before using pixels or coordinates";
            return false;
        }
        return true;
    }

    private static BoundSource FindBinding(JsonElement binding)
    {
        string instance = RequiredString(binding, "source_instance");
        if (!Bindings.TryGetValue(instance, out BoundSource? source))
            throw new InvalidOperationException("binding instance is unknown to this helper generation");
        return source;
    }

    private static void UpdateGeometry(BoundSource source)
    {
        if (source.Lost)
            return;
        if (!IdentityStillCurrent(source.Identity, out string error))
        {
            source.MarkLost(error);
            return;
        }
        RECT rect;
        if (source.Identity.IsWindow)
        {
            if (!GetWindowRect(source.Identity.Hwnd, out rect))
            {
                source.MarkLost("window rectangle is no longer available");
                return;
            }
        }
        else
        {
            if (!TryGetMonitorRect(source.Identity.Monitor, out rect))
            {
                source.MarkLost("display monitor is no longer available");
                return;
            }
        }
        int width = rect.Right - rect.Left;
        int height = rect.Bottom - rect.Top;
        uint dpi = source.Identity.IsWindow ? GetDpiForWindow(source.Identity.Hwnd) : 96;
        if (rect.Left != source.Identity.Left || rect.Top != source.Identity.Top || width != source.Identity.Width ||
            height != source.Identity.Height || dpi != source.Identity.Dpi)
        {
            source.Identity = source.Identity with { Left = rect.Left, Top = rect.Top, Width = width, Height = height, Dpi = dpi };
            Events.AddBoundSource(source.Identity);
            source.GeometryRevision++;
            source.NodeRuntimeIds.Clear();
            source.DisposeCaptureResources();
            source.CaptureUnavailable = null;
            source.AddEvent("geometry_changed", new Dictionary<string, object?> { ["revision"] = source.GeometryRevision });
        }
    }

    private static bool IdentityStillCurrent(SourceIdentity identity, out string reason)
    {
        reason = "";
        if (!identity.IsWindow)
        {
            if (!TryGetMonitorRect(identity.Monitor, out _))
            {
                reason = "display source was detached or removed";
                return false;
            }
            return true;
        }
        if (Events.WindowIncarnation(identity.Hwnd) != identity.WindowInstance)
        {
            reason = "window object incarnation changed";
            return false;
        }
        if (!IsWindow(identity.Hwnd))
        {
            reason = "window was destroyed";
            return false;
        }
        GetWindowThreadProcessId(identity.Hwnd, out uint pidValue);
        if (pidValue != identity.ProcessId)
        {
            reason = "window handle was reused by a different process";
            return false;
        }
        if (GetSessionId(identity.ProcessId, identity.Hwnd) != identity.SessionId)
        {
            reason = "window no longer belongs to the authorized user session";
            return false;
        }
        try
        {
            using Process process = Process.GetProcessById(identity.ProcessId);
            if (process.StartTime.ToUniversalTime().Ticks != identity.ProcessStartTicks)
            {
                reason = "source process incarnation changed";
                return false;
            }
        }
        catch (Exception ex)
        {
            reason = $"source process identity could not be verified: {SafeMessage(ex)}";
            return false;
        }
        return true;
    }

    private static bool TryIdentity(IntPtr hwnd, int pid, out SourceIdentity? identity, out string reason)
    {
        identity = null;
        reason = "";
        if (GetSessionId(pid, hwnd) != SessionId)
        {
            reason = "window is not in this interactive session";
            return false;
        }
        if (!GetWindowRect(hwnd, out RECT rect))
        {
            reason = "window bounds are unavailable";
            return false;
        }
        int width = rect.Right - rect.Left;
        int height = rect.Bottom - rect.Top;
        if (width <= 0 || height <= 0)
        {
            reason = "window has empty geometry";
            return false;
        }
        long startTicks;
        string processName;
        try
        {
            using Process process = Process.GetProcessById(pid);
            startTicks = process.StartTime.ToUniversalTime().Ticks;
            processName = Bounded(process.ProcessName, 128);
        }
        catch (Exception ex)
        {
            reason = $"source process identity is inaccessible: {SafeMessage(ex)}";
            return false;
        }
        string title = ReadWindowText(hwnd);
        string className = ReadClassName(hwnd);
        if (string.IsNullOrWhiteSpace(className))
        {
            reason = "window class could not be identified";
            return false;
        }
        identity = new SourceIdentity(true, hwnd, IntPtr.Zero, pid, startTicks, Events.WindowIncarnation(hwnd), SessionId,
            className, title, processName, "", rect.Left, rect.Top, width, height, GetDpiForWindow(hwnd));
        return true;
    }

    private static bool TryMonitor(IntPtr monitor, out SourceIdentity? identity)
    {
        identity = null;
        if (!GetMonitorInfoW(monitor, out MONITORINFOEX info))
            return false;
        int width = info.Monitor.Right - info.Monitor.Left;
        int height = info.Monitor.Bottom - info.Monitor.Top;
        if (width <= 0 || height <= 0)
            return false;
        identity = new SourceIdentity(false, IntPtr.Zero, monitor, 0, 0, 0, SessionId, "", "",
            "", Bounded(info.Device ?? "display", 128), info.Monitor.Left, info.Monitor.Top, width, height, 96);
        return true;
    }

    private static bool TryGetMonitorRect(IntPtr monitor, out RECT rect)
    {
        rect = default;
        if (!GetMonitorInfoW(monitor, out MONITORINFOEX info))
            return false;
        rect = info.Monitor;
        return true;
    }

    private static bool GetVirtualScreen(out int left, out int top, out int width, out int height)
    {
        left = GetSystemMetrics(76);
        top = GetSystemMetrics(77);
        width = GetSystemMetrics(78);
        height = GetSystemMetrics(79);
        return width > 0 && height > 0;
    }

    private static bool IsForegroundTarget(BoundSource source)
    {
        IntPtr foreground = GetForegroundWindow();
        if (foreground == IntPtr.Zero)
            return false;
        if (source.Identity.IsWindow)
        {
            IntPtr root = GetAncestor(foreground, GA_ROOT);
            return foreground == source.Identity.Hwnd || root == source.Identity.Hwnd || IsChild(source.Identity.Hwnd, foreground);
        }
        if (!GetWindowRect(foreground, out RECT rect))
            return false;
        int left = source.Identity.Left, top = source.Identity.Top;
        int right = left + source.Identity.Width, bottom = top + source.Identity.Height;
        return rect.Left < right && rect.Right > left && rect.Top < bottom && rect.Bottom > top;
    }

    private static bool IsProtectedCaptureWindow(IntPtr hwnd)
    {
        if (hwnd == IntPtr.Zero || !IsWindow(hwnd))
            return false;
        if (GetWindowDisplayAffinity(hwnd, out uint affinity))
            return affinity is 1 or 0x11;
        return false;
    }

    private static bool IsInputDesktopUsable()
    {
        return SessionId != 0 && string.Equals(CurrentInputDesktop(), "Default", StringComparison.Ordinal) &&
               string.Equals(ProcessWindowStation(), "WinSta0", StringComparison.Ordinal);
    }

    private static string CurrentInputDesktop()
    {
        IntPtr desktop = OpenInputDesktop(0, false, DESKTOP_READOBJECTS);
        if (desktop == IntPtr.Zero)
            return "unavailable";
        try { return UserObjectName(desktop); }
        finally { CloseDesktop(desktop); }
    }

    private static string ProcessWindowStation()
    {
        IntPtr station = GetProcessWindowStation();
        return station == IntPtr.Zero ? "unavailable" : UserObjectName(station);
    }

    private static string UserObjectName(IntPtr handle)
    {
        var buffer = new StringBuilder(256);
        if (!GetUserObjectInformationW(handle, UOI_NAME, buffer, (uint)(buffer.Capacity * sizeof(char)), out _))
            return "unavailable";
        return buffer.ToString();
    }

    private static int GetSessionId(int pid, IntPtr hwnd)
    {
        if (hwnd != IntPtr.Zero && GetWindowThreadProcessId(hwnd, out uint hwndPid) != 0 && hwndPid != pid)
            return -1;
        return ProcessIdToSessionId((uint)pid, out uint session) ? checked((int)session) : -1;
    }

    private static string SourceId(SourceIdentity identity)
    {
        string value = identity.IsWindow
            ? $"window:{identity.Hwnd.ToInt64():X}:{identity.ProcessId}:{identity.ProcessStartTicks}:{identity.WindowInstance}:{identity.ClassName}"
            : $"display:{identity.Monitor.ToInt64():X}:{identity.DisplayName}";
        byte[] digest = HMACSHA256.HashData(SourceKey, Encoding.UTF8.GetBytes(value));
        return (identity.IsWindow ? "win-" : "display-") + Convert.ToHexString(digest.AsSpan(0, 16)).ToLowerInvariant();
    }

    private static string EnsureSourceInstance(string sourceId)
    {
        if (!SourceInstances.TryGetValue(sourceId, out string? instance))
        {
            instance = Guid.NewGuid().ToString("N");
            SourceInstances[sourceId] = instance;
        }
        return instance;
    }

    private static GraphicsCaptureItem CreateWindowCaptureItem(IntPtr hwnd)
    {
        if (hwnd == IntPtr.Zero || !IsWindow(hwnd))
            throw new InvalidOperationException("window no longer exists");
        return CreateCaptureItemForNative(hwnd, monitor: false);
    }

    private static GraphicsCaptureItem CreateMonitorCaptureItem(IntPtr monitor)
    {
        if (monitor == IntPtr.Zero)
            throw new InvalidOperationException("display monitor is unavailable");
        return CreateCaptureItemForNative(monitor, monitor: true);
    }

    private static GraphicsCaptureItem CreateCaptureItemForNative(IntPtr handle, bool monitor)
    {
        if (!CaptureSupported)
            throw new InvalidOperationException("Windows.Graphics.Capture.IsSupported returned false");
        IntPtr itemPointer = IntPtr.Zero;
        try
        {
            var factory = GraphicsCaptureItem.As<IGraphicsCaptureItemInterop>();
            Guid iidItem = new("79C3F95B-31F7-4EC2-A464-632EF5D30760");
            if (monitor)
                factory.CreateForMonitor(handle, ref iidItem, out itemPointer);
            else
                factory.CreateForWindow(handle, ref iidItem, out itemPointer);
            return MarshalInterface<GraphicsCaptureItem>.FromAbi(itemPointer);
        }
        finally
        {
            if (itemPointer != IntPtr.Zero) Marshal.Release(itemPointer);
        }
    }

    private static bool QueryCaptureSupport()
    {
        try { return GraphicsCaptureSession.IsSupported(); }
        catch { return false; }
    }

    private static IDirect3DDevice? CreateD3DDevice()
    {
        IntPtr d3d = IntPtr.Zero, context = IntPtr.Zero, dxgi = IntPtr.Zero, inspectable = IntPtr.Zero;
        try
        {
            int hr = D3D11CreateDevice(IntPtr.Zero, D3D_DRIVER_TYPE_HARDWARE, IntPtr.Zero,
                D3D11_CREATE_DEVICE_BGRA_SUPPORT, IntPtr.Zero, 0, D3D11_SDK_VERSION,
                out d3d, out _, out context);
            if (hr < 0 || d3d == IntPtr.Zero)
            {
                D3DCreateFailure = $"D3D11CreateDevice failed (HRESULT 0x{hr:X8})";
                return null;
            }
            Guid dxgiIid = new("54EC77FA-1377-44E6-8C32-88FD5F44C84C");
            Marshal.ThrowExceptionForHR(Marshal.QueryInterface(d3d, in dxgiIid, out dxgi));
            Marshal.ThrowExceptionForHR(CreateDirect3D11DeviceFromDXGIDevice(dxgi, out inspectable));
            return MarshalInterface<IDirect3DDevice>.FromAbi(inspectable);
        }
        catch (Exception ex)
        {
            D3DCreateFailure = SafeMessage(ex);
            return null;
        }
        finally
        {
            if (inspectable != IntPtr.Zero) Marshal.Release(inspectable);
            if (dxgi != IntPtr.Zero) Marshal.Release(dxgi);
            if (context != IntPtr.Zero) Marshal.Release(context);
            if (d3d != IntPtr.Zero) Marshal.Release(d3d);
        }
    }

    private static bool SetPhysicalDpiAwareness()
    {
        try
        {
            bool set = SetProcessDpiAwarenessContext(new IntPtr(-4));
            if (set)
                return true;
            IntPtr context = GetThreadDpiAwarenessContext();
            return AreDpiAwarenessContextsEqual(context, new IntPtr(-4));
        }
        catch { return false; }
    }

    private static bool ValidSize(int width, int height)
    {
        return width > 0 && height > 0 && width <= MaxSide && height <= MaxSide && (long)width * height * 4 <= MaxFrameBytes;
    }

    private static Dictionary<string, object?> Bounds(int left, int top, int width, int height) =>
        new() { ["x"] = left, ["y"] = top, ["width"] = width, ["height"] = height };

    private static Dictionary<string, object?>? RectBounds(System.Windows.Rect rect)
    {
        if (rect.IsEmpty || !double.IsFinite(rect.X) || !double.IsFinite(rect.Y) ||
            !double.IsFinite(rect.Width) || !double.IsFinite(rect.Height) ||
            rect.Width < 0 || rect.Height < 0)
            return null;
        return new() { ["x"] = rect.X, ["y"] = rect.Y, ["width"] = rect.Width, ["height"] = rect.Height };
    }

    private static string WindowId(IntPtr hwnd) => hwnd == IntPtr.Zero ? "none" : $"window:{hwnd.ToInt64():X}";

    private static string ReadWindowText(IntPtr hwnd)
    {
        int length = Math.Clamp(GetWindowTextLengthW(hwnd), 0, 512);
        var text = new StringBuilder(length + 1);
        if (length > 0) GetWindowTextW(hwnd, text, text.Capacity);
        return Bounded(text.ToString(), 512);
    }

    private static string ReadClassName(IntPtr hwnd)
    {
        var text = new StringBuilder(256);
        GetClassNameW(hwnd, text, text.Capacity);
        return Bounded(text.ToString(), 256);
    }

    private static string Bounded(string? value, int maximum)
    {
        if (string.IsNullOrEmpty(value)) return "";
        string normalized = value.Replace('\0', ' ').Trim();
        return normalized.Length <= maximum ? normalized : normalized[..maximum];
    }

    private static long MonotonicNs() => QpcTicksToNs(Stopwatch.GetTimestamp());
    private static long QpcTicksToNs(long ticks) => checked((long)((decimal)ticks * 1_000_000_000m / QpcFrequency));
    private static long TimeSpanTicksToNs(long ticks) => checked(ticks * 100);

    private static bool AuthenticateClient(NamedPipeServerStream pipe, int expectedPid, out string? reason)
    {
        reason = null;
        IntPtr handle = pipe.SafePipeHandle.DangerousGetHandle();
        if (!GetNamedPipeClientProcessId(handle, out uint clientPid) || clientPid != expectedPid)
        {
            reason = "named-pipe client process does not match the requesting entity";
            return false;
        }
        if (!GetNamedPipeClientSessionId(handle, out uint clientSession) || clientSession != SessionId || SessionId == 0)
        {
            reason = "named-pipe client is not in the helper's nonzero interactive session";
            return false;
        }
        if (!TryGetProcessSid((int)clientPid, out string clientSid) || !string.Equals(clientSid, UserSid, StringComparison.Ordinal))
        {
            reason = "named-pipe client SID does not match the helper user SID";
            return false;
        }
        return true;
    }

    private static bool TryGetProcessSid(int pid, out string sid)
    {
        sid = "";
        IntPtr process = OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, false, (uint)pid);
        if (process == IntPtr.Zero)
            return false;
        IntPtr token = IntPtr.Zero;
        try
        {
            if (!OpenProcessToken(process, TOKEN_QUERY, out token))
                return false;
            using var identity = new WindowsIdentity(token);
            sid = identity.User?.Value ?? "";
            return sid.Length > 0;
        }
        catch { return false; }
        finally
        {
            if (token != IntPtr.Zero) CloseHandle(token);
            CloseHandle(process);
        }
    }

    private static byte[]? ReadMessage(Stream stream)
    {
        byte[] prefix = new byte[4];
        int first = stream.Read(prefix, 0, prefix.Length);
        if (first == 0)
            return null;
        ReadRemainder(stream, prefix, first);
        int count = BitConverter.ToInt32(prefix);
        if (count <= 0 || count > MaxHeaderBytes)
            throw new InvalidDataException("control message is outside the configured size bound");
        byte[] json = new byte[count];
        ReadRemainder(stream, json, 0);
        byte[] payloadLengthBytes = new byte[4];
        ReadRemainder(stream, payloadLengthBytes, 0);
        int payloadLength = BitConverter.ToInt32(payloadLengthBytes);
        if (payloadLength != 0)
            throw new InvalidDataException("requests may not carry an unnegotiated binary payload");
        return json;
    }

    private static void ReadRemainder(Stream stream, byte[] buffer, int offset)
    {
        while (offset < buffer.Length)
        {
            int read = stream.Read(buffer, offset, buffer.Length - offset);
            if (read == 0)
                throw new EndOfStreamException("named-pipe client disconnected during a message");
            offset += read;
        }
    }

    private static void WriteMessage(Stream stream, Dictionary<string, object?> response, byte[] payload)
    {
        byte[] json = JsonSerializer.SerializeToUtf8Bytes(response);
        if (json.Length > MaxHeaderBytes || payload.Length > MaxFrameBytes)
            throw new InvalidDataException("helper response exceeds the configured frame size");
        stream.Write(BitConverter.GetBytes(json.Length));
        stream.Write(json);
        stream.Write(BitConverter.GetBytes(payload.Length));
        if (payload.Length > 0)
            stream.Write(payload);
        stream.Flush();
    }

    private static Dictionary<string, object?> Ok(params (string key, object? value)[] values)
    {
        var result = new Dictionary<string, object?> { ["ok"] = true };
        foreach ((string key, object? value) in values) result[key] = value;
        return result;
    }

    private static Dictionary<string, object?> Error(string kind, string message) =>
        new() { ["ok"] = false, ["error"] = new Dictionary<string, object?> { ["kind"] = kind, ["message"] = message } };

    private static Dictionary<string, object?> Rejected(string reason) =>
        new() { ["disposition"] = "rejected", ["delivered_count"] = 0, ["ack_strength"] = "none", ["detail"] = reason };

    private static string SafeMessage(Exception exception)
    {
        string message = exception.GetBaseException().Message;
        return Bounded(string.IsNullOrWhiteSpace(message) ? exception.GetType().Name : message, 512);
    }

    private static bool IsInputOperation(string? operation) => operation is
        "keyboard.key" or "keyboard.text" or "pointer.absolute" or "pointer.relative" or "pointer.button" or "pointer.wheel";

    private static JsonElement RequiredObject(JsonElement parent, string name)
    {
        if (!parent.TryGetProperty(name, out JsonElement value) || value.ValueKind != JsonValueKind.Object)
            throw new ArgumentException($"{name} must be an object");
        return value;
    }

    private static string RequiredString(JsonElement parent, string name)
    {
        if (!parent.TryGetProperty(name, out JsonElement value) || value.ValueKind != JsonValueKind.String || string.IsNullOrWhiteSpace(value.GetString()))
            throw new ArgumentException($"{name} must be nonempty text");
        return value.GetString()!;
    }

    private static bool RequiredBoolean(JsonElement parent, string name)
    {
        if (!parent.TryGetProperty(name, out JsonElement value)
            || value.ValueKind is not (JsonValueKind.True or JsonValueKind.False))
            throw new ArgumentException($"{name} must be a boolean");
        return value.GetBoolean();
    }

    private static string? GetString(JsonElement parent, string name)
    {
        return parent.TryGetProperty(name, out JsonElement value) && value.ValueKind == JsonValueKind.String ? value.GetString() : null;
    }

    private static long GetLong(JsonElement parent, string name)
    {
        return parent.TryGetProperty(name, out JsonElement value) && value.TryGetInt64(out long number) ? number : long.MinValue;
    }

    private static int RequiredInt(JsonElement parent, string name, int min, int max)
    {
        if (!parent.TryGetProperty(name, out JsonElement value) || !value.TryGetInt32(out int number) || number < min || number > max)
            throw new ArgumentException($"{name} must be an integer in {min}..{max}");
        return number;
    }

    private const uint D3D11_CREATE_DEVICE_BGRA_SUPPORT = 0x20;
    private const uint D3D11_SDK_VERSION = 7;
    private const int D3D_DRIVER_TYPE_HARDWARE = 1;
    private const uint DESKTOP_READOBJECTS = 0x0001;
    private const int UOI_NAME = 2;
    private const uint PROCESS_QUERY_LIMITED_INFORMATION = 0x1000;
    private const uint TOKEN_QUERY = 0x0008;
    private const uint GA_ROOT = 2;
    private const uint MOUSEEVENTF_MOVE = 0x0001;
    private const uint MOUSEEVENTF_LEFTDOWN = 0x0002;
    private const uint MOUSEEVENTF_LEFTUP = 0x0004;
    private const uint MOUSEEVENTF_RIGHTDOWN = 0x0008;
    private const uint MOUSEEVENTF_RIGHTUP = 0x0010;
    private const uint MOUSEEVENTF_MIDDLEDOWN = 0x0020;
    private const uint MOUSEEVENTF_MIDDLEUP = 0x0040;
    private const uint MOUSEEVENTF_WHEEL = 0x0800;
    private const uint MOUSEEVENTF_HWHEEL = 0x01000;
    private const uint MOUSEEVENTF_ABSOLUTE = 0x8000;
    private const uint MOUSEEVENTF_VIRTUALDESK = 0x4000;
    private const uint KEYEVENTF_KEYUP = 0x0002;
    private const uint KEYEVENTF_UNICODE = 0x0004;
    private const uint INPUT_KEYBOARD = 1;
    private const uint INPUT_MOUSE = 0;

    private static INPUT KeyInput(ushort vk, bool keyUp) => new()
    {
        Type = INPUT_KEYBOARD,
        Union = new INPUTUNION { Keyboard = new KEYBDINPUT { Vk = vk, Flags = keyUp ? KEYEVENTF_KEYUP : 0, ExtraInfo = new UIntPtr(InjectionCookie) } },
    };

    private static INPUT UnicodeInput(char unit, bool keyUp) => new()
    {
        Type = INPUT_KEYBOARD,
        Union = new INPUTUNION { Keyboard = new KEYBDINPUT { Scan = unit, Flags = KEYEVENTF_UNICODE | (keyUp ? KEYEVENTF_KEYUP : 0), ExtraInfo = new UIntPtr(InjectionCookie) } },
    };

    private static INPUT MouseInput(int dx, int dy, uint data, uint flags) => new()
    {
        Type = INPUT_MOUSE,
        Union = new INPUTUNION { Mouse = new MOUSEINPUT { Dx = dx, Dy = dy, MouseData = data, Flags = flags, ExtraInfo = new UIntPtr(InjectionCookie) } },
    };

    private static INPUT ButtonInput(string button, bool down)
    {
        uint flags = button switch
        {
            "left" => down ? MOUSEEVENTF_LEFTDOWN : MOUSEEVENTF_LEFTUP,
            "middle" => down ? MOUSEEVENTF_MIDDLEDOWN : MOUSEEVENTF_MIDDLEUP,
            "right" => down ? MOUSEEVENTF_RIGHTDOWN : MOUSEEVENTF_RIGHTUP,
            _ => throw new ArgumentException("pointer button must be left, middle, or right"),
        };
        return MouseInput(0, 0, 0, flags);
    }

    [StructLayout(LayoutKind.Sequential)]
    private struct INPUT { public uint Type; public INPUTUNION Union; }
    [StructLayout(LayoutKind.Explicit)]
    private struct INPUTUNION
    {
        [FieldOffset(0)] public MOUSEINPUT Mouse;
        [FieldOffset(0)] public KEYBDINPUT Keyboard;
        [FieldOffset(0)] public HARDWAREINPUT Hardware;
    }
    [StructLayout(LayoutKind.Sequential)]
    private struct MOUSEINPUT { public int Dx, Dy; public uint MouseData, Flags, Time; public UIntPtr ExtraInfo; }
    [StructLayout(LayoutKind.Sequential)]
    private struct KEYBDINPUT { public ushort Vk, Scan; public uint Flags, Time; public UIntPtr ExtraInfo; }
    [StructLayout(LayoutKind.Sequential)]
    private struct HARDWAREINPUT { public uint Msg; public ushort ParamL, ParamH; }
    [ComImport, Guid("5B0D3235-4DBA-4D44-865E-8F1D0E4FD04D"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
    private unsafe interface IMemoryBufferByteAccess { void GetBuffer(out byte* buffer, out uint capacity); }
    [ComImport, Guid("3628E81B-3CAC-4C60-B7F4-23CE0E0C3356"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
    private interface IGraphicsCaptureItemInterop
    {
        void CreateForWindow(IntPtr window, ref Guid iid, out IntPtr item);
        void CreateForMonitor(IntPtr monitor, ref Guid iid, out IntPtr item);
    }

    private static INPUT? NoInputPlaceholder => null;

    [DllImport("user32.dll", SetLastError = true)] private static extern bool EnumWindows(EnumWindowsProc callback, IntPtr data);
    private delegate bool EnumWindowsProc(IntPtr hwnd, IntPtr data);
    [DllImport("user32.dll", SetLastError = true)] private static extern bool EnumDisplayMonitors(IntPtr dc, IntPtr clip, MonitorEnumProc callback, IntPtr data);
    private delegate bool MonitorEnumProc(IntPtr monitor, IntPtr dc, IntPtr rect, IntPtr data);
    [DllImport("user32.dll", SetLastError = true)] private static extern bool GetWindowRect(IntPtr hwnd, out RECT rect);
    [DllImport("user32.dll", SetLastError = true)] private static extern bool IsWindow(IntPtr hwnd);
    [DllImport("user32.dll", SetLastError = true)] private static extern bool IsWindowVisible(IntPtr hwnd);
    [DllImport("user32.dll", SetLastError = true)] private static extern bool IsIconic(IntPtr hwnd);
    [DllImport("user32.dll", CharSet = CharSet.Unicode, SetLastError = true)] private static extern int GetWindowTextW(IntPtr hwnd, StringBuilder text, int maxCount);
    [DllImport("user32.dll", SetLastError = true)] private static extern int GetWindowTextLengthW(IntPtr hwnd);
    [DllImport("user32.dll", CharSet = CharSet.Unicode, SetLastError = true)] private static extern int GetClassNameW(IntPtr hwnd, StringBuilder className, int maxCount);
    [DllImport("user32.dll", SetLastError = true)] private static extern uint GetWindowThreadProcessId(IntPtr hwnd, out uint processId);
    [DllImport("user32.dll", SetLastError = true)] private static extern IntPtr GetForegroundWindow();
    [DllImport("user32.dll", SetLastError = true)] private static extern IntPtr GetAncestor(IntPtr hwnd, uint flags);
    [DllImport("user32.dll", SetLastError = true)] private static extern bool IsChild(IntPtr parent, IntPtr child);
    [DllImport("user32.dll", SetLastError = true)] private static extern uint GetDpiForWindow(IntPtr hwnd);
    [DllImport("user32.dll", SetLastError = true)] private static extern int GetSystemMetrics(int index);
    [DllImport("user32.dll", SetLastError = true)] private static extern uint SendInput(uint count, INPUT[] inputs, int size);
    [DllImport("user32.dll", SetLastError = true)] private static extern IntPtr OpenInputDesktop(uint flags, bool inherit, uint desiredAccess);
    [DllImport("user32.dll", SetLastError = true)] private static extern bool CloseDesktop(IntPtr desktop);
    [DllImport("user32.dll", SetLastError = true)] private static extern IntPtr GetProcessWindowStation();
    [DllImport("user32.dll", CharSet = CharSet.Unicode, SetLastError = true)] private static extern bool GetUserObjectInformationW(IntPtr handle, int index, StringBuilder info, uint length, out uint needed);
    [DllImport("user32.dll", SetLastError = true)] private static extern bool GetWindowDisplayAffinity(IntPtr hwnd, out uint affinity);
    [DllImport("user32.dll", EntryPoint = "GetMonitorInfoW", SetLastError = true)] private static extern bool NativeGetMonitorInfoW(IntPtr monitor, ref MONITORINFOEX info);
    private static bool GetMonitorInfoW(IntPtr monitor, out MONITORINFOEX info)
    {
        info = new MONITORINFOEX { Size = Marshal.SizeOf<MONITORINFOEX>() };
        return NativeGetMonitorInfoW(monitor, ref info);
    }
    [DllImport("user32.dll", SetLastError = true)] private static extern bool SetProcessDpiAwarenessContext(IntPtr context);
    [DllImport("user32.dll")] private static extern IntPtr GetThreadDpiAwarenessContext();
    [DllImport("user32.dll")] private static extern bool AreDpiAwarenessContextsEqual(IntPtr first, IntPtr second);
    [DllImport("kernel32.dll", SetLastError = true)] private static extern bool ProcessIdToSessionId(uint processId, out uint sessionId);
    [DllImport("kernel32.dll", SetLastError = true)] private static extern bool GetNamedPipeClientProcessId(IntPtr pipe, out uint clientPid);
    [DllImport("kernel32.dll", SetLastError = true)] private static extern bool GetNamedPipeClientSessionId(IntPtr pipe, out uint clientSessionId);
    [DllImport("kernel32.dll", SetLastError = true)] private static extern IntPtr OpenProcess(uint access, bool inherit, uint pid);
    [DllImport("advapi32.dll", SetLastError = true)] private static extern bool OpenProcessToken(IntPtr process, uint access, out IntPtr token);
    [DllImport("kernel32.dll", SetLastError = true)] private static extern bool CloseHandle(IntPtr handle);
    [DllImport("combase.dll", PreserveSig = true)] private static extern int RoInitialize(uint initType);
    [DllImport("combase.dll")] private static extern void RoUninitialize();

    [DllImport("d3d11.dll", PreserveSig = true)] private static extern int D3D11CreateDevice(IntPtr adapter, int driverType, IntPtr software, uint flags, IntPtr featureLevels, uint featureLevelCount, uint sdkVersion, out IntPtr device, out uint featureLevel, out IntPtr immediateContext);
    [DllImport("d3d11.dll", PreserveSig = true)] private static extern int CreateDirect3D11DeviceFromDXGIDevice(IntPtr dxgiDevice, out IntPtr graphicsDevice);

    [StructLayout(LayoutKind.Sequential)] private struct RECT { public int Left, Top, Right, Bottom; }
    [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Unicode)]
    private struct MONITORINFOEX
    {
        public int Size; public RECT Monitor; public RECT Work; public uint Flags;
        [MarshalAs(UnmanagedType.ByValTStr, SizeConst = 32)] public string? Device;
    }

    private sealed record SourceIdentity(bool IsWindow, IntPtr Hwnd, IntPtr Monitor, int ProcessId,
        long ProcessStartTicks, long WindowInstance, int SessionId, string ClassName, string Title, string ProcessName,
        string DisplayName, int Left, int Top, int Width, int Height, uint Dpi);

    private sealed class BoundSource : IDisposable
    {
        public string SourceId { get; }
        public string SourceInstance { get; }
        public long SourceEpoch { get; } = 1;
        public string EnvironmentIncarnation { get; }
        public SourceIdentity Identity { get; set; }
        public long GeometryRevision { get; set; } = 1;
        public int Width { get; private set; }
        public int Height { get; private set; }
        public GraphicsCaptureItem? Item { get; set; }
        public CaptureResources? Resources { get; set; }
        public string? CaptureUnavailable { get; set; }
        public bool Lost { get; private set; }
        public bool FollowForeground { get; set; }
        public bool Demonstration { get; set; }
        public bool DemonstrationIncomplete { get; set; }
        public long DemonstrationLostCount { get; set; }
        public long DemonstrationMissingIntervals { get; set; }
        public string? DemonstrationStopReason { get; set; }
        public string? LossReason { get; private set; }
        public long CaptureSequence { get; set; }
        public long? LastSampleNs { get; set; }
        public long LastEventSequence { get; set; }
        public bool UiaTimedOut { get; set; }
        public bool UiaAvailable { get; set; }
        public object NodeLock { get; } = new();
        public Dictionary<string, int[]> NodeRuntimeIds { get; set; } = new(StringComparer.Ordinal);
        public HashSet<int> OwnedKeys { get; } = new();
        public HashSet<string> OwnedButtons { get; } = new(StringComparer.Ordinal);
        private readonly EventMonitor _events;

        public BoundSource(string sourceId, SourceIdentity identity, string environment, EventMonitor events, string sourceInstance)
        {
            SourceId = sourceId; SourceInstance = sourceInstance; Identity = identity;
            EnvironmentIncarnation = environment; _events = events;
            Width = identity.Width; Height = identity.Height;
            _events.AddBoundSource(identity);
            AddEvent("bound", new Dictionary<string, object?> { ["kind"] = identity.IsWindow ? "window" : "display" });
        }

        public void SetCapturedSize(int width, int height)
        {
            if (width != Width || height != Height)
                InvalidateGeometry(width, height);
        }

        public void InvalidateGeometry(int width, int height)
        {
            if (width > 0 && height > 0)
            {
                Width = width; Height = height;
            }
            GeometryRevision++;
            _events.InvalidateDemonstrationGeometry(this);
            NodeRuntimeIds.Clear();
            DisposeCaptureResources();
            AddEvent("geometry_changed", new Dictionary<string, object?> { ["revision"] = GeometryRevision, ["width"] = Width, ["height"] = Height });
        }

        public CaptureResources GetCaptureResources()
        {
            if (Resources is not null)
                return Resources;
            if (Item is null || D3DDevice is null)
                throw new InvalidOperationException("capture item or D3D device is unavailable");
            Resources = new CaptureResources(D3DDevice, Item, Width, Height);
            return Resources;
        }

        public void MarkLost(string reason)
        {
            if (Lost) return;
            Lost = true; LossReason = reason;
            FollowForeground = false; Demonstration = false;
            _events.RemoveBoundSource(this);
            AddEvent("source_lost", new Dictionary<string, object?> { ["reason"] = reason });
            DisposeCaptureResources();
            Item = null;
            NodeRuntimeIds.Clear();
            UiaAvailable = false;
        }

        public void AddEvent(string kind, Dictionary<string, object?> detail) => _events.Record(kind, Identity.Hwnd, Identity.IsWindow, detail);
        public void DisposeCaptureResources()
        {
            Resources?.Dispose(); Resources = null;
        }
        public void Dispose()
        {
            FollowForeground = false; Demonstration = false;
            _events.RemoveBoundSource(this);
            DisposeCaptureResources();
            Item = null;
            foreach (int key in OwnedKeys.ToArray()) OwnedKeys.Remove(key);
            foreach (string button in OwnedButtons.ToArray()) OwnedButtons.Remove(button);
        }
    }

    private sealed class CaptureResources : IDisposable
    {
        public Direct3D11CaptureFramePool Pool { get; }
        public GraphicsCaptureSession Session { get; }
        public ManualResetEvent FrameArrived { get; } = new(false);
        public long LastSampleTicks { get; set; }
        public long Sequence { get; set; }
        private readonly TypedEventHandler<Direct3D11CaptureFramePool, object> _handler;
        private bool _started;

        public CaptureResources(IDirect3DDevice device, GraphicsCaptureItem item, int width, int height)
        {
            Pool = Direct3D11CaptureFramePool.CreateFreeThreaded(device,
                DirectXPixelFormat.B8G8R8A8UIntNormalized, 2, new SizeInt32 { Width = width, Height = height });
            _handler = (_, _) => FrameArrived.Set();
            Pool.FrameArrived += _handler;
            Session = Pool.CreateCaptureSession(item);
            Session.IsCursorCaptureEnabled = true;
        }

        public void Start()
        {
            if (_started) return;
            _started = true;
            Session.StartCapture();
        }

        public void Dispose()
        {
            try { Pool.FrameArrived -= _handler; } catch { }
            try { Session.Dispose(); } catch { }
            try { Pool.Dispose(); } catch { }
            FrameArrived.Dispose();
        }
    }

    private sealed class EventMonitor
    {
        private const uint EVENT_SYSTEM_FOREGROUND = 0x0003;
        private const uint EVENT_OBJECT_DESTROY = 0x8001;
        private const uint EVENT_OBJECT_LOCATIONCHANGE = 0x800B;
        private const uint WINEVENT_OUTOFCONTEXT = 0;
        private const int WH_KEYBOARD_LL = 13;
        private const int WH_MOUSE_LL = 14;
        private const int HC_ACTION = 0;
        private const int WM_KEYDOWN = 0x0100, WM_KEYUP = 0x0101, WM_SYSKEYDOWN = 0x0104, WM_SYSKEYUP = 0x0105;
        private const int WM_LBUTTONDOWN = 0x0201, WM_LBUTTONUP = 0x0202, WM_RBUTTONDOWN = 0x0204, WM_RBUTTONUP = 0x0205;
        private const int WM_MBUTTONDOWN = 0x0207, WM_MBUTTONUP = 0x0208, WM_MOUSEMOVE = 0x0200, WM_MOUSEWHEEL = 0x020A, WM_MOUSEHWHEEL = 0x020E;
        private const uint LLKHF_INJECTED = 0x10, LLMHF_INJECTED = 0x01;
        private const uint WM_QUIT = 0x0012;
        private readonly object _lock = new();
        private readonly Queue<SurfaceEvent> _events = new();
        private readonly Queue<IntPtr> _generationOrder = new();
        private readonly Dictionary<IntPtr, long> _windowGenerations = new();
        private readonly HashSet<IntPtr> _boundWindows = new();
        private readonly Dictionary<IntPtr, RECT> _boundDisplays = new();
        private readonly Dictionary<(IntPtr Handle, bool IsWindow), HumanActivity> _humanActivity = new();
        private const int MaxDemonstrationScopes = 32;
        private const int MaxDemonstrationEvents = 256;
        private readonly Dictionary<string, DemonstrationScope> _demonstrations = new(StringComparer.Ordinal);
        private bool _shiftDown, _controlDown, _altDown, _windowsDown;
        private readonly HashSet<uint> _demonstrationDownKeys = new();
        private readonly ManualResetEventSlim _ready = new(false);
        private readonly Thread _thread;
        private readonly WinEventProc _winEventProc;
        private readonly HookProc _keyboardProc;
        private readonly HookProc _mouseProc;
        private volatile bool _running;
        private long _sequence;
        private int _nativeThreadId;
        private long _focusEpoch;
        private IntPtr _focusWindow;
        private IntPtr _foregroundHook, _destroyHook, _locationHook, _keyboardHook, _mouseHook;
        private bool _inputHooksAvailable;
        public bool InputHooksAvailable => Volatile.Read(ref _inputHooksAvailable);
        public bool LifecycleHooksAvailable { get; private set; }

        public EventMonitor()
        {
            _winEventProc = OnWinEvent;
            _keyboardProc = OnKeyboard;
            _mouseProc = OnMouse;
            _thread = new Thread(MessageLoop) { IsBackground = true, Name = "Cassi Windows Surface events" };
        }

        public void Start()
        {
            _running = true;
            _thread.Start();
            _ready.Wait(TimeSpan.FromSeconds(2));
        }

        public void Stop()
        {
            _running = false;
            if (_thread.IsAlive && _nativeThreadId != 0)
                PostThreadMessage(_nativeThreadId, WM_QUIT, UIntPtr.Zero, IntPtr.Zero);
            if (_thread.IsAlive)
                _thread.Join(750);
        }

        public void AddBoundSource(SourceIdentity identity)
        {
            lock (_lock)
            {
                if (identity.IsWindow)
                    _boundWindows.Add(identity.Hwnd);
                else if (TryGetMonitorRect(identity.Monitor, out RECT rect))
                    _boundDisplays[identity.Monitor] = rect;
            }
        }

        public void RemoveBoundSource(BoundSource source)
        {
            RetireDemonstration(source, "source binding released");
            lock (_lock)
            {
                if (source.Identity.IsWindow)
                    _boundWindows.Remove(source.Identity.Hwnd);
                else
                    _boundDisplays.Remove(source.Identity.Monitor);
                _humanActivity.Remove((source.Identity.IsWindow ? source.Identity.Hwnd : source.Identity.Monitor,
                    source.Identity.IsWindow));
            }
        }

        public bool EnableDemonstration(BoundSource source)
        {
            if (!InputHooksAvailable || source.Lost || !source.FollowForeground)
                return false;
            long focusEpoch = FocusEpoch;
            lock (_lock)
            {
                if (_demonstrations.TryGetValue(source.SourceInstance, out DemonstrationScope? existing))
                    return ReferenceEquals(existing.Source, source) &&
                        existing.GeometryRevision == source.GeometryRevision && source.Demonstration;
                if (!_running || !InputHooksAvailable || source.Lost || !source.FollowForeground ||
                    _demonstrations.Count >= MaxDemonstrationScopes)
                    return false;
                _demonstrations[source.SourceInstance] = new DemonstrationScope(
                    source, focusEpoch, source.GeometryRevision);
                source.Demonstration = true;
                return true;
            }
        }

        public (List<Dictionary<string, object?>> Events, Dictionary<string, object?> Coverage)
            RemoveDemonstration(BoundSource source)
        {
            lock (_lock)
            {
                if (!_demonstrations.Remove(source.SourceInstance, out DemonstrationScope? scope))
                {
                    source.Demonstration = false;
                    return (new(), DemonstrationCoverageLocked(source, null));
                }
                source.Demonstration = false;
                List<Dictionary<string, object?>> events = scope.Events.ToList();
                Dictionary<string, object?> coverage = DemonstrationCoverageLocked(source, scope);
                source.DemonstrationLostCount = 0;
                source.DemonstrationMissingIntervals = 0;
                source.DemonstrationIncomplete = false;
                source.DemonstrationStopReason = null;
                return (events, coverage);
            }
        }

        public void InvalidateDemonstrationGeometry(BoundSource source) =>
            RetireDemonstration(source, "source geometry changed");

        public (List<Dictionary<string, object?>> Events, Dictionary<string, object?> Coverage)
            CaptureDemonstration(BoundSource source, long expectedFocusEpoch, long expectedInputEpoch)
        {
            bool foreground = source.FollowForeground && IsForegroundSource(source.Identity);
            lock (_lock)
            {
                if (!_demonstrations.TryGetValue(source.SourceInstance, out DemonstrationScope? scope))
                {
                    source.Demonstration = false;
                    return (new(), DemonstrationCoverageLocked(source, null));
                }
                if (!source.Demonstration || source.Lost || !source.FollowForeground ||
                    scope.GeometryRevision != source.GeometryRevision)
                {
                    RetireDemonstrationLocked(source, scope, "source geometry or identity changed");
                    return (new(), DemonstrationCoverageLocked(source, null));
                }
                if (!foreground)
                {
                    if (scope.WasForeground)
                        scope.MissingIntervals++;
                    scope.WasForeground = false;
                    scope.Gesture = null;
                    return (new(), DemonstrationCoverageLocked(source, scope));
                }
                scope.WasForeground = true;
                var events = new List<Dictionary<string, object?>>(scope.Events.Count);
                while (scope.Events.TryDequeue(out Dictionary<string, object?>? item))
                {
                    if (!Equals(item.GetValueOrDefault("focus_epoch"), expectedFocusEpoch) ||
                        !Equals(item.GetValueOrDefault("input_domain_epoch"), expectedInputEpoch))
                    {
                        scope.LostCount++;
                        continue;
                    }
                    events.Add(item);
                }
                Dictionary<string, object?> coverage = DemonstrationCoverageLocked(source, scope);
                scope.LostCount = 0;
                scope.MissingIntervals = 0;
                source.DemonstrationLostCount = 0;
                source.DemonstrationMissingIntervals = 0;
                source.DemonstrationIncomplete = false;
                source.DemonstrationStopReason = null;
                return (events, coverage);
            }
        }

        public Dictionary<string, object?> DemonstrationStatus(BoundSource source, bool markMissing = false)
        {
            lock (_lock)
            {
                _demonstrations.TryGetValue(source.SourceInstance, out DemonstrationScope? scope);
                if (markMissing && scope is not null && scope.WasForeground)
                {
                    scope.MissingIntervals++;
                    scope.WasForeground = false;
                    scope.Gesture = null;
                }
                return DemonstrationCoverageLocked(source, scope);
            }
        }

        private void RetireDemonstration(BoundSource source, string reason)
        {
            lock (_lock)
            {
                if (_demonstrations.TryGetValue(source.SourceInstance, out DemonstrationScope? scope))
                    RetireDemonstrationLocked(source, scope, reason);
                else
                    source.Demonstration = false;
            }
        }

        private void RetireDemonstrationLocked(BoundSource source, DemonstrationScope scope, string reason)
        {
            _demonstrations.Remove(source.SourceInstance);
            source.Demonstration = false;
            source.DemonstrationIncomplete = true;
            source.DemonstrationLostCount += scope.LostCount + scope.Events.Count + 1;
            source.DemonstrationMissingIntervals += scope.MissingIntervals;
            source.DemonstrationStopReason = reason;
            scope.Events.Clear();
            scope.Gesture = null;
        }

        private Dictionary<string, object?> DemonstrationCoverageLocked(
            BoundSource source, DemonstrationScope? scope)
        {
            long lost = source.DemonstrationLostCount + (scope?.LostCount ?? 0);
            long missing = source.DemonstrationMissingIntervals + (scope?.MissingIntervals ?? 0);
            bool enabled = scope is not null && source.Demonstration && source.FollowForeground && !source.Lost;
            return new Dictionary<string, object?>
            {
                ["enabled"] = enabled,
                ["complete"] = !source.DemonstrationIncomplete && lost == 0 && missing == 0,
                ["lost_count"] = lost,
                ["missing_intervals"] = missing,
                ["source_instance"] = source.SourceInstance,
                ["source_epoch"] = source.SourceEpoch,
                ["geometry_revision"] = scope?.GeometryRevision ?? source.GeometryRevision,
                ["focus_epoch"] = scope?.FocusEpoch ?? FocusEpoch,
                ["event_focus_epoch"] = FocusEpoch,
                ["reason"] = source.DemonstrationStopReason,
            };
        }
 

        public long WindowIncarnation(IntPtr hwnd)
        {
            lock (_lock)
                return _windowGenerations.GetValueOrDefault(hwnd);
        }

        public long FocusEpoch
        {
            get
            {
                IntPtr current = GetAncestor(GetForegroundWindow(), GA_ROOT);
                lock (_lock)
                {
                    if (current != _focusWindow)
                    {
                        _focusWindow = current;
                        _focusEpoch++;
                    }
                    return _focusEpoch;
                }
            }
        }

        public (long Epoch, bool Active) HumanState(SourceIdentity identity)
        {
            var key = (identity.IsWindow ? identity.Hwnd : identity.Monitor, identity.IsWindow);
            long now = Stopwatch.GetTimestamp();
            lock (_lock)
            {
                if (!_humanActivity.TryGetValue(key, out HumanActivity activity))
                    return (0, false);
                bool active = now - activity.LastTicks <= Stopwatch.Frequency * 2L;
                return (activity.Epoch, active);
            }
        }

        public void Record(string kind, IntPtr hwnd, bool isWindow, Dictionary<string, object?> detail)
        {
            lock (_lock)
            {
                _events.Enqueue(new SurfaceEvent(++_sequence, kind, hwnd, isWindow, MonotonicNs(), detail));
                while (_events.Count > 1024)
                    _events.Dequeue();
            }
        }

        public List<Dictionary<string, object?>> Since(IntPtr handle, bool isWindow, long after)
        {
            lock (_lock)
                return _events.Where(item => item.Sequence > after && EventMatches(item, handle, isWindow))
                    .Select(item => item.ToDictionary()).ToList();
        }

        private bool EventMatches(SurfaceEvent item, IntPtr handle, bool isWindow)
        {
            return item.Hwnd == handle && item.IsWindow == isWindow;
        }

        private void MessageLoop()
        {
            _nativeThreadId = checked((int)GetCurrentThreadId());
            PeekMessageW(out _, IntPtr.Zero, 0, 0, 0);
            _foregroundHook = SetWinEventHook(EVENT_SYSTEM_FOREGROUND, EVENT_SYSTEM_FOREGROUND, IntPtr.Zero, _winEventProc, 0, 0, WINEVENT_OUTOFCONTEXT);
            _destroyHook = SetWinEventHook(EVENT_OBJECT_DESTROY, EVENT_OBJECT_DESTROY, IntPtr.Zero, _winEventProc, 0, 0, WINEVENT_OUTOFCONTEXT);
            _locationHook = SetWinEventHook(EVENT_OBJECT_LOCATIONCHANGE, EVENT_OBJECT_LOCATIONCHANGE, IntPtr.Zero, _winEventProc, 0, 0, WINEVENT_OUTOFCONTEXT);
            LifecycleHooksAvailable = _foregroundHook != IntPtr.Zero && _destroyHook != IntPtr.Zero && _locationHook != IntPtr.Zero;
            IntPtr module = GetModuleHandleW(null);
            _keyboardHook = SetWindowsHookExW(WH_KEYBOARD_LL, _keyboardProc, module, 0);
            _mouseHook = SetWindowsHookExW(WH_MOUSE_LL, _mouseProc, module, 0);
            Volatile.Write(ref _inputHooksAvailable, _keyboardHook != IntPtr.Zero && _mouseHook != IntPtr.Zero);
            _ready.Set();
            while (_running && GetMessageW(out MSG message, IntPtr.Zero, 0, 0) > 0)
            {
                TranslateMessage(ref message);
                DispatchMessageW(ref message);
            }
            if (_foregroundHook != IntPtr.Zero) UnhookWinEvent(_foregroundHook);
            if (_destroyHook != IntPtr.Zero) UnhookWinEvent(_destroyHook);
            if (_locationHook != IntPtr.Zero) UnhookWinEvent(_locationHook);
            if (_keyboardHook != IntPtr.Zero) UnhookWindowsHookEx(_keyboardHook);
            if (_mouseHook != IntPtr.Zero) UnhookWindowsHookEx(_mouseHook);
        }

        private void OnWinEvent(IntPtr hook, uint eventType, IntPtr hwnd, int idObject, int idChild, uint eventThread, uint eventTime)
        {
            if (eventType == EVENT_SYSTEM_FOREGROUND)
            {
                IntPtr current = GetAncestor(hwnd, GA_ROOT);
                lock (_lock)
                {
                    if (current != _focusWindow)
                    {
                        _focusWindow = current;
                        _focusEpoch++;
                    }
                }
                MarkDemonstrationFocusGaps();
            }
            if (eventType == EVENT_OBJECT_DESTROY && hwnd != IntPtr.Zero && idObject == 0 && idChild == 0)
            {
                lock (_lock)
                {
                    if (!_windowGenerations.ContainsKey(hwnd))
                        _generationOrder.Enqueue(hwnd);
                    _windowGenerations[hwnd] = _windowGenerations.GetValueOrDefault(hwnd) + 1;
                    while (_generationOrder.Count > 8192)
                        _windowGenerations.Remove(_generationOrder.Dequeue());
                }
            }
            if (eventType == EVENT_OBJECT_DESTROY && hwnd != IntPtr.Zero && idObject == 0 && idChild == 0)
                RetireWindowDemonstrations(hwnd, "source window was destroyed");
            if (eventType == EVENT_OBJECT_LOCATIONCHANGE && hwnd != IntPtr.Zero && idObject == 0 && idChild == 0)
                InvalidateResizedWindowDemonstrations(hwnd);
            string kind = eventType switch
            {
                EVENT_SYSTEM_FOREGROUND => "foreground_changed",
                EVENT_OBJECT_DESTROY => "object_destroyed",
                EVENT_OBJECT_LOCATIONCHANGE => "object_location_changed",
                _ => "windows_event",
            };
            Record(kind, hwnd, true, new Dictionary<string, object?> { ["event_id"] = eventType, ["object_id"] = idObject, ["child_id"] = idChild });
        }

        private void MarkDemonstrationFocusGaps()
        {
            List<DemonstrationScope> scopes;
            lock (_lock)
                scopes = _demonstrations.Values.ToList();
            foreach (DemonstrationScope scope in scopes)
            {
                bool foreground = scope.Source.FollowForeground && IsForegroundSource(scope.Source.Identity);
                lock (_lock)
                {
                    if (!_demonstrations.TryGetValue(scope.Source.SourceInstance, out DemonstrationScope? active) ||
                        !ReferenceEquals(active, scope))
                        continue;
                    if (scope.WasForeground && !foreground)
                    {
                        scope.MissingIntervals++;
                        scope.LostCount += scope.Events.Count;
                        scope.Events.Clear();
                        scope.Gesture = null;
                    }
                    scope.WasForeground = foreground;
                }
            }
        }

        private void RetireWindowDemonstrations(IntPtr hwnd, string reason)
        {
            List<DemonstrationScope> scopes;
            lock (_lock)
                scopes = _demonstrations.Values.ToList();
            foreach (DemonstrationScope scope in scopes)
                if (scope.Source.Identity.IsWindow && scope.Source.Identity.Hwnd == hwnd)
                    RetireDemonstration(scope.Source, reason);
        }

        private void InvalidateResizedWindowDemonstrations(IntPtr hwnd)
        {
            List<DemonstrationScope> scopes;
            lock (_lock)
                scopes = _demonstrations.Values.ToList();
            foreach (DemonstrationScope scope in scopes)
            {
                BoundSource source = scope.Source;
                if (!source.Identity.IsWindow || source.Identity.Hwnd != hwnd)
                    continue;
                if (!GetWindowRect(hwnd, out RECT bounds) ||
                    bounds.Right - bounds.Left != source.Width || bounds.Bottom - bounds.Top != source.Height)
                    InvalidateDemonstrationGeometry(source);
            }
        }

        private IntPtr OnKeyboard(int code, UIntPtr message, IntPtr data)
        {
            int msg = unchecked((int)message.ToUInt64());
            if (code == HC_ACTION && msg is WM_KEYDOWN or WM_SYSKEYDOWN or WM_KEYUP or WM_SYSKEYUP)
            {
                KBDLLHOOKSTRUCT key = Marshal.PtrToStructure<KBDLLHOOKSTRUCT>(data);
                if ((key.Flags & LLKHF_INJECTED) == 0)
                {
                    RecordNonInjectedInput("keyboard");
                    RecordDemonstrationKeyboard(key.VkCode,
                        msg is WM_KEYDOWN or WM_SYSKEYDOWN);
                }
            }
            return CallNextHookEx(_keyboardHook, code, message, data);
        }

        private IntPtr OnMouse(int code, UIntPtr message, IntPtr data)
        {
            int msg = unchecked((int)message.ToUInt64());
            if (code == HC_ACTION && msg is WM_LBUTTONDOWN or WM_LBUTTONUP or WM_RBUTTONDOWN or WM_RBUTTONUP or WM_MBUTTONDOWN or WM_MBUTTONUP or WM_MOUSEMOVE or WM_MOUSEWHEEL or WM_MOUSEHWHEEL)
            {
                MSLLHOOKSTRUCT mouse = Marshal.PtrToStructure<MSLLHOOKSTRUCT>(data);
                if ((mouse.Flags & LLMHF_INJECTED) == 0)
                {
                    RecordNonInjectedInput("pointer");
                    RecordDemonstrationMouse(msg, mouse);
                }
            }
            return CallNextHookEx(_mouseHook, code, message, data);
        }

        private void RecordDemonstrationKeyboard(uint virtualKey, bool down)
        {
            lock (_lock)
            {
                bool firstDown = down
                    ? _demonstrationDownKeys.Add(virtualKey)
                    : _demonstrationDownKeys.Remove(virtualKey);
                UpdateModifierState(virtualKey, down);
                if (!down || !firstDown || IsModifierKey(virtualKey))
                    return;
                bool commandModifier = _controlDown || _altDown || _windowsDown;
                string? key = SafeShortcutKey(virtualKey);
                if (!commandModifier && key is null)
                    return;
                var detail = new Dictionary<string, object?>
                {
                    ["action"] = commandModifier ? "shortcut" : "non-text-key",
                    ["key"] = key ?? "printable-key-omitted",
                    ["modifiers"] = CurrentModifiers(),
                };
                foreach (DemonstrationScope scope in _demonstrations.Values.ToArray())
                    if (scope.Source.FollowForeground && IsForegroundSource(scope.Source.Identity))
                        AppendDemonstrationEventLocked(scope, "shortcut", detail);
            }
        }

        private void RecordDemonstrationMouse(int message, MSLLHOOKSTRUCT mouse)
        {
            List<DemonstrationScope> scopes;
            lock (_lock)
                scopes = _demonstrations.Values.ToList();
            foreach (DemonstrationScope scope in scopes)
            {
                BoundSource source = scope.Source;
                if (!source.FollowForeground || !IsForegroundSource(source.Identity))
                    continue;
                bool inside = TryDemonstrationPoint(scope, mouse.Point, out int x, out int y, out bool geometryChanged);
                if (geometryChanged)
                {
                    InvalidateDemonstrationGeometry(source);
                    continue;
                }
                string? downButton = message switch
                {
                    WM_LBUTTONDOWN => "primary",
                    WM_RBUTTONDOWN => "secondary",
                    WM_MBUTTONDOWN => "middle",
                    _ => null,
                };
                string? upButton = message switch
                {
                    WM_LBUTTONUP => "primary",
                    WM_RBUTTONUP => "secondary",
                    WM_MBUTTONUP => "middle",
                    _ => null,
                };
                if (downButton is not null)
                {
                    if (!inside) continue;
                    lock (_lock)
                    {
                        if (_demonstrations.TryGetValue(source.SourceInstance, out DemonstrationScope? current) &&
                            ReferenceEquals(current, scope))
                            scope.Gesture = new MouseGesture(downButton, x, y, mouse.Point.X, mouse.Point.Y);
                    }
                    continue;
                }
                if (message == WM_MOUSEMOVE)
                {
                    lock (_lock)
                    {
                        if (scope.Gesture is MouseGesture gesture)
                        {
                            long dx = mouse.Point.X - gesture.StartScreenX;
                            long dy = mouse.Point.Y - gesture.StartScreenY;
                            if (dx * dx + dy * dy >= 64)
                                gesture.Dragging = true;
                        }
                    }
                    continue;
                }
                if (upButton is not null)
                {
                    MouseGesture? gesture = null;
                    lock (_lock)
                    {
                        if (scope.Gesture is MouseGesture pending &&
                            string.Equals(pending.Button, upButton, StringComparison.Ordinal))
                        {
                            gesture = pending;
                            scope.Gesture = null;
                        }
                    }
                    if (gesture is null) continue;
                    bool dragging = gesture.Dragging ||
                        Math.Abs((long)mouse.Point.X - gesture.StartScreenX) >= 8 ||
                        Math.Abs((long)mouse.Point.Y - gesture.StartScreenY) >= 8;
                    var detail = new Dictionary<string, object?> { ["button"] = gesture.Button };
                    if (dragging)
                    {
                        detail["start"] = new Dictionary<string, object?> { ["x"] = gesture.StartX, ["y"] = gesture.StartY };
                        detail["end"] = inside ? new Dictionary<string, object?> { ["x"] = x, ["y"] = y } : null;
                        detail["end_inside_source"] = inside;
                        AppendDemonstrationEvent(scope, "drag", detail);
                    }
                    else if (inside)
                    {
                        detail["x"] = gesture.StartX;
                        detail["y"] = gesture.StartY;
                        AppendDemonstrationEvent(scope, "click", detail);
                    }
                    continue;
                }
                if (message is WM_MOUSEWHEEL or WM_MOUSEHWHEEL && inside)
                {
                    short delta = unchecked((short)((mouse.MouseData >> 16) & 0xffff));
                    if (delta == 0) continue;
                    AppendDemonstrationEvent(scope, "scroll", new Dictionary<string, object?>
                    {
                        ["x"] = x, ["y"] = y,
                        ["axis"] = message == WM_MOUSEWHEEL ? "vertical" : "horizontal",
                        ["direction"] = message == WM_MOUSEWHEEL
                            ? delta > 0 ? "up" : "down"
                            : delta > 0 ? "right" : "left",
                    });
                }
            }
        }

        private bool TryDemonstrationPoint(
            DemonstrationScope scope, POINT point, out int x, out int y, out bool geometryChanged)
        {
            x = y = 0;
            geometryChanged = false;
            BoundSource source = scope.Source;
            if (source.Lost || !source.Demonstration || source.GeometryRevision != scope.GeometryRevision)
            {
                geometryChanged = source.GeometryRevision != scope.GeometryRevision;
                return false;
            }
            RECT bounds;
            if (source.Identity.IsWindow)
            {
                if (!GetWindowRect(source.Identity.Hwnd, out bounds))
                    return false;
            }
            else if (!TryGetMonitorRect(source.Identity.Monitor, out bounds))
            {
                return false;
            }
            int width = bounds.Right - bounds.Left;
            int height = bounds.Bottom - bounds.Top;
            if (width != source.Width || height != source.Height)
            {
                geometryChanged = true;
                return false;
            }
            if (point.X < bounds.Left || point.X >= bounds.Right ||
                point.Y < bounds.Top || point.Y >= bounds.Bottom)
                return false;
            if (source.Identity.IsWindow)
            {
                IntPtr hit = WindowFromPoint(point);
                IntPtr root = hit == IntPtr.Zero ? IntPtr.Zero : GetAncestor(hit, GA_ROOT);
                if (root != source.Identity.Hwnd && hit != source.Identity.Hwnd &&
                    !IsChild(source.Identity.Hwnd, hit))
                    return false;
            }
            x = (int)Math.Clamp((long)(point.X - bounds.Left) * source.Width / width, 0, source.Width - 1);
            y = (int)Math.Clamp((long)(point.Y - bounds.Top) * source.Height / height, 0, source.Height - 1);
            return true;
        }

        private void AppendDemonstrationEvent(
            DemonstrationScope scope, string kind, Dictionary<string, object?> detail)
        {
            lock (_lock)
                AppendDemonstrationEventLocked(scope, kind, detail);
        }

        private void AppendDemonstrationEventLocked(
            DemonstrationScope scope, string kind, Dictionary<string, object?> detail)
        {
            if (!_demonstrations.TryGetValue(scope.Source.SourceInstance, out DemonstrationScope? active) ||
                !ReferenceEquals(scope, active) || !scope.Source.Demonstration)
                return;
            if (scope.Events.Count >= MaxDemonstrationEvents)
            {
                scope.Events.Dequeue();
                scope.LostCount++;
            }
            scope.Events.Enqueue(new Dictionary<string, object?>
            {
                ["sequence"] = ++_sequence,
                ["kind"] = kind,
                ["time_ns"] = MonotonicNs(),
                ["focus_epoch"] = FocusEpoch,
                ["input_domain_epoch"] = HumanState(scope.Source.Identity).Epoch,
                ["event_time_uncertainty_ns"] = null,
                ["source_id"] = scope.Source.SourceId,
                ["source_instance"] = scope.Source.SourceInstance,
                ["source_epoch"] = scope.Source.SourceEpoch,
                ["geometry_revision"] = scope.GeometryRevision,
                ["detail"] = detail,
            });
        }

        private static bool IsModifierKey(uint virtualKey) =>
            virtualKey is 0x10 or 0x11 or 0x12 or 0xA0 or 0xA1 or 0xA2 or 0xA3 or 0x5B or 0x5C;

        private void UpdateModifierState(uint virtualKey, bool down)
        {
            switch (virtualKey)
            {
                case 0x10: case 0xA0: case 0xA1: _shiftDown = down; break;
                case 0x11: case 0xA2: case 0xA3: _controlDown = down; break;
                case 0x12: _altDown = down; break;
                case 0x5B: case 0x5C: _windowsDown = down; break;
            }
        }

        private List<string> CurrentModifiers()
        {
            var modifiers = new List<string>(4);
            if (_controlDown) modifiers.Add("ctrl");
            if (_altDown) modifiers.Add("alt");
            if (_shiftDown) modifiers.Add("shift");
            if (_windowsDown) modifiers.Add("windows");
            return modifiers;
        }

        private static string? SafeShortcutKey(uint virtualKey) => virtualKey switch
        {
            0x1B => "escape", 0x09 => "tab", 0x0D => "enter", 0x08 => "backspace",
            0x2E => "delete", 0x2D => "insert", 0x24 => "home", 0x23 => "end",
            0x21 => "pageup", 0x22 => "pagedown", 0x25 => "left", 0x26 => "up",
            0x27 => "right", 0x28 => "down", 0x2C => "printscreen",
            >= 0x70 and <= 0x87 => $"f{virtualKey - 0x6F}",
            _ => null,
        };

        private void RecordNonInjectedInput(string channel)
        {
            IntPtr foreground = GetForegroundWindow();
            IntPtr root = GetAncestor(foreground, GA_ROOT);
            var targets = new HashSet<(IntPtr Handle, bool IsWindow)>();
            RECT foregroundRect = default;
            bool hasRect = root != IntPtr.Zero && GetWindowRect(root, out foregroundRect);
            lock (_lock)
            {
                foreach (IntPtr hwnd in _boundWindows)
                    if (root == hwnd || foreground == hwnd || IsChild(hwnd, foreground))
                        targets.Add((hwnd, true));
                if (hasRect)
                {
                    foreach ((IntPtr monitor, RECT bounds) in _boundDisplays)
                        if (foregroundRect.Left < bounds.Right && foregroundRect.Right > bounds.Left &&
                            foregroundRect.Top < bounds.Bottom && foregroundRect.Bottom > bounds.Top)
                            targets.Add((monitor, false));
                }
            }

            long now = Stopwatch.GetTimestamp();
            foreach ((IntPtr handle, bool isWindow) in targets)
            {
                var key = (handle, isWindow);
                long epoch;
                lock (_lock)
                {
                    HumanActivity activity = _humanActivity.GetValueOrDefault(key);
                    if (activity.LastTicks == 0 || now - activity.LastTicks > Stopwatch.Frequency * 2L)
                        activity.Epoch++;
                    activity.LastTicks = now;
                    _humanActivity[key] = activity;
                    epoch = activity.Epoch;
                }
                Record("physical_input", handle, isWindow, new Dictionary<string, object?>
                {
                    ["channel"] = channel,
                    ["origin"] = "Windows low-level hook marks this event non-injected; a human actor is not uniquely proven",
                    ["human_control_epoch"] = epoch,
                    ["key_or_pointer_data"] = "not recorded",
                });
            }
        }

        private sealed class DemonstrationScope
        {
            public BoundSource Source { get; }
            public long FocusEpoch { get; }
            public long GeometryRevision { get; }
            public Queue<Dictionary<string, object?>> Events { get; } = new();
            public long LostCount { get; set; }
            public long MissingIntervals { get; set; }
            public bool WasForeground { get; set; }
            public MouseGesture? Gesture { get; set; }

            public DemonstrationScope(BoundSource source, long focusEpoch, long geometryRevision)
            {
                Source = source;
                FocusEpoch = focusEpoch;
                GeometryRevision = geometryRevision;
                WasForeground = IsForegroundSource(source.Identity);
            }
        }

        private sealed class MouseGesture
        {
            public string Button { get; }
            public int StartX { get; }
            public int StartY { get; }
            public int StartScreenX { get; }
            public int StartScreenY { get; }
            public bool Dragging { get; set; }

            public MouseGesture(string button, int x, int y, int screenX, int screenY)
            {
                Button = button;
                StartX = x;
                StartY = y;
                StartScreenX = screenX;
                StartScreenY = screenY;
            }
        }

        private struct HumanActivity { public long Epoch; public long LastTicks; }
        [UnmanagedFunctionPointer(CallingConvention.Winapi)] private delegate void WinEventProc(IntPtr hook, uint eventType, IntPtr hwnd, int idObject, int idChild, uint eventThread, uint eventTime);
        [UnmanagedFunctionPointer(CallingConvention.Winapi)] private delegate IntPtr HookProc(int code, UIntPtr message, IntPtr data);
        [StructLayout(LayoutKind.Sequential)] private struct MSG { public IntPtr Hwnd; public uint Message; public UIntPtr WParam; public IntPtr LParam; public uint Time; public POINT Point; public uint Private; }
        [StructLayout(LayoutKind.Sequential)] private struct POINT { public int X, Y; }
        [DllImport("user32.dll", SetLastError = true)] private static extern IntPtr WindowFromPoint(POINT point);
        [StructLayout(LayoutKind.Sequential)] private struct KBDLLHOOKSTRUCT { public uint VkCode, ScanCode, Flags, Time; public UIntPtr ExtraInfo; }
        [StructLayout(LayoutKind.Sequential)] private struct MSLLHOOKSTRUCT { public POINT Point; public uint MouseData, Flags, Time; public UIntPtr ExtraInfo; }
        [DllImport("user32.dll", SetLastError = true)] private static extern IntPtr SetWinEventHook(uint eventMin, uint eventMax, IntPtr module, WinEventProc callback, uint processId, uint threadId, uint flags);
        [DllImport("user32.dll", SetLastError = true)] private static extern bool UnhookWinEvent(IntPtr hook);
        [DllImport("user32.dll", SetLastError = true)] private static extern IntPtr SetWindowsHookExW(int hookId, HookProc callback, IntPtr module, uint threadId);
        [DllImport("user32.dll", SetLastError = true)] private static extern bool UnhookWindowsHookEx(IntPtr hook);
        [DllImport("user32.dll")] private static extern IntPtr CallNextHookEx(IntPtr hook, int code, UIntPtr wParam, IntPtr lParam);
        [DllImport("user32.dll", SetLastError = true)] private static extern int GetMessageW(out MSG message, IntPtr hwnd, uint min, uint max);
        [DllImport("user32.dll", SetLastError = true)] private static extern bool PeekMessageW(out MSG message, IntPtr hwnd, uint min, uint max, uint remove);
        [DllImport("user32.dll")] private static extern bool TranslateMessage(ref MSG message);
        [DllImport("user32.dll")] private static extern IntPtr DispatchMessageW(ref MSG message);
        [DllImport("user32.dll", SetLastError = true)] private static extern bool PostThreadMessage(int threadId, uint message, UIntPtr wParam, IntPtr lParam);
        [DllImport("kernel32.dll")] private static extern uint GetCurrentThreadId();
        [DllImport("kernel32.dll", CharSet = CharSet.Unicode)] private static extern IntPtr GetModuleHandleW(string? moduleName);
    }

    private sealed record SurfaceEvent(long Sequence, string Kind, IntPtr Hwnd, bool IsWindow, long TimeNs, Dictionary<string, object?> Detail)
    {
        public IntPtr TargetRoot => Hwnd;
        public Dictionary<string, object?> ToDictionary() => new()
        {
            ["sequence"] = Sequence, ["kind"] = Kind, ["time_ns"] = TimeNs,
            ["source_handle"] = Hwnd == IntPtr.Zero ? null : $"0x{Hwnd.ToInt64():X}",
            ["detail"] = Detail,
        };
    }
}
