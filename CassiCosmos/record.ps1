# Background recording launcher (Godot 4 Movie Maker batch job).
#
# Runs the recorder scene with the console exe at a fixed fps and writes
# an AVI; the scene quits itself when the requested frame count is reached
# and Movie Maker finalizes the file. Run from godot/space-sim:
#
#   powershell -File record.ps1 -Out myvideo.avi -Duration 60
#
# Param values of 0 (or -1 for Gravity/Init) mean "leave the scene default".
#
# Movie Maker quirk (verified 2026-08-11 against the shipped main.cpp and
# empirically): the AVI resolution is read from the PROJECT SETTINGS
# display/window/size/viewport_width/height at engine start -- NOT from the
# window size (neither --resolution nor a runtime window resize changes the
# movie size, and the window_width_override pair is DPI-scaled into weird
# sizes on this machine). This launcher temporarily patches the two
# viewport settings in project.godot for the run and restores the file
# afterwards (a leftover .recbak from a crashed run is cleaned up on the
# next launch).

param(
    [string]$Out = "recording.avi",
    [int]$Fps = 30,
    [int]$Duration = 30,
    [int]$Grid = 0,
    [int]$Particles = 0,
    [int]$Gravity = -1,
    [int]$Init = -1,
    [int]$Steps = 0,
    [int]$Color = -1,
    [string]$Aspect = "",
    [string]$Resolution = "1920x1080",
    [string]$Scene = "res://scenes/main_recorder.tscn",
    [string]$Exe = "C:/Users/Carina/AppData/Local/Microsoft/WinGet/Packages/GodotEngine.GodotEngine.Mono_Microsoft.Winget.Source_8wekyb3d8bbwe/Godot_v4.7.1-stable_mono_win64/Godot_v4.7.1-stable_mono_win64_console.exe"
)

$resParts = $Resolution.Split("x")
if ($resParts.Count -ne 2) { Write-Error "-Resolution must be WxH (e.g. 1920x1080)"; exit 1 }
$resW = [int]$resParts[0]; $resH = [int]$resParts[1]

# -- Temporarily patch project.godot with the movie resolution ----------
$proj = Join-Path $Pwd "project.godot"
$backup = "$proj.recbak"
if (Test-Path $backup) {
    # Crashed run left a backup: restore first, then patch fresh.
    Move-Item $backup $proj -Force
}
if (Test-Path $proj) {
    Copy-Item $proj $backup -Force
    $lines = [System.Collections.Generic.List[string]]::new()
    foreach ($line in [System.IO.File]::ReadAllLines($proj)) {
        if ($line -match "^window/size/viewport_(width|height)=") {
            continue  # drop the current values; re-insert patched below
        }
        $lines.Add($line)
    }
    # Insert the resolution right after the [display] section header.
    $patched = $false
    for ($i = 0; $i -lt $lines.Count; $i++) {
        if ($lines[$i] -match "^\[display\]\s*$") {
            $lines.Insert($i + 1, "window/size/viewport_width=$resW")
            $lines.Insert($i + 2, "window/size/viewport_height=$resH")
            $patched = $true
            break
        }
    }
    if (-not $patched) {
        $lines.Add("")
        $lines.Add("[display]")
        $lines.Add("window/size/viewport_width=$resW")
        $lines.Add("window/size/viewport_height=$resH")
    }
    [System.IO.File]::WriteAllLines($proj, $lines)
    Write-Host "Patched project.godot viewport to ${resW}x${resH} (restored after the run)."
} else {
    Write-Warning "project.godot not found at $proj -- movie size will use the project default."
}

# -- Build the Godot command --
$userArgs = @("--record-frames=$([int]($Duration * $Fps))", "--record-fps=$Fps")
if ($Grid -gt 0)      { $userArgs += "--grid=$Grid" }
if ($Particles -gt 0) { $userArgs += "--particles=$Particles" }
if ($Gravity -ge 0)   { $userArgs += "--gravity=$Gravity" }
if ($Init -ge 0)      { $userArgs += "--init=$Init" }
if ($Steps -gt 0)     { $userArgs += "--steps=$Steps" }
if ($Color -ge 0)     { $userArgs += "--color=$Color" }
if ($Aspect -ne "")   { $userArgs += "--aspect=$Aspect" }

$argsList = @("--path", "$Pwd", "--write-movie", $Out, "--fixed-fps", "$Fps", $Scene, "--") + $userArgs

Write-Host ""
Write-Host "Running: $Exe $($argsList -join ' ')"
Write-Host ""

try {
    & $Exe @argsList
    $ec = $LASTEXITCODE
} finally {
    if (Test-Path $backup) {
        Move-Item $backup $proj -Force
        Write-Host "Restored project.godot."
    }
}
exit $ec
