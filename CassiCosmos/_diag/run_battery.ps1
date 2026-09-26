# ============================================================================
# run_battery.ps1 -- CassiCosmos GPU regression battery (one command)
# ============================================================================
# Runs every verify scene WINDOWED via the bench console (launcher-stub rule:
# Start-Process + redirect + WaitForExit -- NEVER pipe, NEVER --headless for
# GPU scenes), asserts each scene's printed check total, scans stdout+stderr
# for failure markers, and prints a per-scene PASS/FAIL table. Exits nonzero
# if ANY scene failed (harness gate: $LASTEXITCODE).
#
# PRE-BATTERY (do these once before running, after any compute/*.glsl or
# scripts/*.gd change):
#   1. .glsl import refresh -- re-import the compute shaders so the pipeline
#      push-constant/binding layout matches the current source (the stale-
#      import trap that produced "push constant size mismatch" floods):
#        & <bench>\Godot_v4.7.1-stable_win64_console.exe --headless --import --path <root>
#      (imports are non-GPU; --headless is fine here)
#   2. Script syntax gate:
#        & <bench>\Godot_v4.7.1-stable_win64_console.exe --headless --check-only --script res://scripts/cassi_sim.gd
#        & <bench>\Godot_v4.7.1-stable_win64_console.exe --headless --check-only --script res://scripts/cassi_physics_engine.gd
#      (both must exit 0 / print only the engine banner)
#   3. Layout-contract gate (M0 commit 1 — the class-killer; run before the
#      scenes; also executed by this script below):
#        & <bench>\Godot_v4.7.1-stable_win64_console.exe --headless --script res://scripts/contracts/assert_layout.gd
#      (exit 0 = every covered shader's push-constant float count, binding
#      lists, header line and every host PackedByteArray allocation match
#      scripts/contracts/layout.gd — catches the merge 64-vs-92-B class)
#   4. Make sure no other Godot GAME instance is running (this script waits
#      for that anyway); the owner's EDITOR (CommandLine contains --editor)
#      is exempt and never touched.
#
# Scene table -- expected = the verify script's printed check total
#   (numerator of "N/N checks passed" / the "checks=" value):
#     verify_gravity_modes.tscn          58
#     verify_river_law.tscn              17
#     verify_merge.tscn                   8
#     verify_merge_sim.tscn               5
#     verify_merge_engine.tscn            7
#     verify_bh_accretion_engine.tscn     9
#     verify_exclusive_scan.tscn          4
#   plus a final scenes/main.tscn smoke (--quit-after 180, no count assert).
#
# Usage:
#   powershell -ExecutionPolicy Bypass -File _diag\run_battery.ps1
# ============================================================================

param(
    [int]$MainSmokeFrames = 180,
    [switch]$SkipMainSmoke
)

$ErrorActionPreference = 'Continue'

# --- resolve root from script location ($PSScriptRoot = _diag, root = ..) ---
$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$exe  = Join-Path $PSScriptRoot 'godot_bench\Godot_v4.7.1-stable_win64_console.exe'

if (-not (Test-Path $exe)) {
    Write-Host "[battery] FATAL: bench console not found: $exe" -ForegroundColor Red
    exit 2
}

# ---------------------------------------------------------------------------
# Scene table: Scene (res path), Expected (check total), Kind (log format)
#   'nn'     -> "RESULT: N/N checks passed, M failed"
#   'checks' -> "checks=N failures=M elapsed=K ms" + "RESULT: PASS|FAIL"
#   'scan'   -> "RESULT: PASS (checks=N failures=M)"
# ---------------------------------------------------------------------------
$scenes = @(
    @{ Scene = 'res://scenes/verify_gravity_modes.tscn';      Expected = 58; Kind = 'nn' },
    @{ Scene = 'res://scenes/verify_river_law.tscn';          Expected = 17; Kind = 'nn' },
    @{ Scene = 'res://scenes/verify_merge.tscn';              Expected = 8;  Kind = 'checks' },
    @{ Scene = 'res://scenes/verify_merge_sim.tscn';          Expected = 5;  Kind = 'checks' },
    @{ Scene = 'res://scenes/verify_merge_engine.tscn';       Expected = 7;  Kind = 'checks' },
    @{ Scene = 'res://scenes/verify_bh_accretion_engine.tscn'; Expected = 9;  Kind = 'checks' },
    @{ Scene = 'res://scenes/verify_exclusive_scan.tscn';     Expected = 4;  Kind = 'scan' }
)

# Fatal markers scanned across stdout + stderr (besides per-check [FAIL] lines)
$fatalPatterns = @(
    'push constant size mismatch',
    'device lost',
    'Vulkan device was lost',
    'TDR'
)

# ---------------------------------------------------------------------------
# Layout-contract gate (M0 commit 1): the schema assert runs BEFORE any
# scene — a mismatch here aborts the battery (the class-killer for the
# push-constant/binding drift class).
# ---------------------------------------------------------------------------
$al = & $exe --headless --script 'res://scripts/contracts/assert_layout.gd' 2>&1 | Out-String
Write-Host ($al.Trim())
if ($LASTEXITCODE -ne 0) {
    Write-Host "[battery] FATAL: layout-contract assert failed (see above) -- aborting" -ForegroundColor Red
    exit 2
}

# ---------------------------------------------------------------------------
# Wait for the GPU: any Godot instance not running with --editor blocks.
# ---------------------------------------------------------------------------
function Wait-GpuFree {
    param([string]$SceneName)
    for ($i = 0; $i -lt 12; $i++) {
        $g = Get-CimInstance Win32_Process -Filter "Name LIKE '%Godot%'" -ErrorAction SilentlyContinue
        $others = @($g | Where-Object { -not $_.CommandLine -or $_.CommandLine -notlike '*--editor*' })
        if ($others.Count -eq 0) { return $true }
        if ($i -eq 0) {
            Write-Host ("[battery] {0} other Godot instance(s) running -- waiting up to 120 s before {1}" -f $others.Count, $SceneName) -ForegroundColor Yellow
        }
        Start-Sleep -Seconds 10
    }
    Write-Host "[battery] WARNING: other Godot instances still running after 120 s -- proceeding (results may contend)" -ForegroundColor Yellow
    return $false
}

# ---------------------------------------------------------------------------
# Run one scene windowed; returns stdout log path.
# ---------------------------------------------------------------------------
function Invoke-Scene {
    param([string]$ScenePath, [string]$LogBase, [int]$QuitAfter = 0)
    $log = Join-Path $root ("_diag\{0}.log" -f $LogBase)
    $err = "$log.err"
    Remove-Item $log, $err -ErrorAction SilentlyContinue
    $argList = @('--path', $root)
    if ($QuitAfter -gt 0) { $argList += @('--quit-after', [string]$QuitAfter) }
    $argList += $ScenePath
    $p = Start-Process -FilePath $exe -ArgumentList $argList -NoNewWindow `
        -RedirectStandardOutput $log -RedirectStandardError $err -PassThru
    $p.WaitForExit()
    $p.Refresh()
    Start-Sleep -Milliseconds 300
    # The bench console exe is a LAUNCHER STUB: its exit code is sometimes
    # not propagated to $p.ExitCode (null). The substantive gate is the
    # printed check totals + failure markers; a null exit code is not a
    # scene failure (the stub already forwarded the child's result).
    $code = $p.ExitCode
    if ($null -eq $code) { $code = 0 }
    return @{ Log = $log; Err = $err; ExitCode = $code }
}

# ---------------------------------------------------------------------------
# Parse the printed check total per the scene's log kind.
# Returns $null when no total line is found; otherwise
#   @{ Checks = int; Failures = int; Raw = '...' }
# ---------------------------------------------------------------------------
function Get-TotalCount {
    param([string]$LogPath, [string]$Kind)
    if (-not (Test-Path $LogPath)) { return $null }
    $text = Get-Content $LogPath -Raw -ErrorAction SilentlyContinue
    if (-not $text) { return $null }
    if ($Kind -eq 'nn') {
        $m = [regex]::Match($text, 'RESULT:\s*(\d+)/(\d+) checks passed,\s*(\d+) failed')
        if ($m.Success) {
            return @{ Checks = [int]$m.Groups[1].Value; Failures = [int]$m.Groups[3].Value; Raw = $m.Value.Trim() }
        }
    } elseif ($Kind -eq 'scan') {
        $m = [regex]::Match($text, 'RESULT:\s*(PASS|FAIL)\s*\(checks=(\d+)\s+failures=(\d+)\)')
        if ($m.Success) {
            return @{ Checks = [int]$m.Groups[2].Value; Failures = [int]$m.Groups[3].Value; Raw = $m.Value.Trim() }
        }
    } else { # 'checks' -- merge family: take the LAST "checks=N failures=M" line
        $ms = [regex]::Matches($text, 'checks=(\d+)\s+failures=(\d+)\s+elapsed=(\d+)\s+ms')
        if ($ms.Count -gt 0) {
            $m = $ms[$ms.Count - 1]
            return @{ Checks = [int]$m.Groups[1].Value; Failures = [int]$m.Groups[2].Value; Raw = $m.Value.Trim() }
        }
        $m2 = [regex]::Match($text, 'RESULT:\s*(PASS|FAIL)')
        if ($m2.Success) {
            $failFlag = 0
            if ($m2.Groups[1].Value -eq 'FAIL') { $failFlag = 1 }
            return @{ Checks = -1; Failures = $failFlag; Raw = $m2.Value.Trim() }
        }
    }
    return $null
}

# ---------------------------------------------------------------------------
# Failure-marker scan: fatal patterns in stdout+stderr, plus per-check [FAIL]
# line count (RESULT lines are excluded by construction -- they carry "0 failed").
# ---------------------------------------------------------------------------
function Get-FailureMarkers {
    param([string]$LogPath, [string]$ErrPath)
    $markers = @()
    foreach ($f in @($LogPath, $ErrPath)) {
        if (-not (Test-Path $f)) { continue }
        $leaf = Split-Path $f -Leaf
        foreach ($pat in $fatalPatterns) {
            $hits = Select-String -Path $f -SimpleMatch -Pattern $pat -ErrorAction SilentlyContinue
            if ($hits) { $markers += ("{0}: '{1}' x{2}" -f $leaf, $pat, @($hits).Count) }
        }
        $failLines = @(Select-String -Path $f -Pattern '\[FAIL\]' -ErrorAction SilentlyContinue)
        if ($failLines.Count -gt 0) { $markers += ("{0}: per-check [FAIL] x{1}" -f $leaf, $failLines.Count) }
    }
    return $markers
}

# ---------------------------------------------------------------------------
# Battery
# ---------------------------------------------------------------------------
Write-Host "=== CassiCosmos regression battery ===" -ForegroundColor Cyan
Write-Host ("root: {0}" -f $root)
Write-Host ("exe:  {0}" -f $exe)
Write-Host ""

$results = @()

foreach ($s in $scenes) {
    $name = [System.IO.Path]::GetFileNameWithoutExtension($s.Scene)
    $logBase = "battery_$name"
    Write-Host ("--- {0} (expect {1}) ---" -f $name, $s.Expected)
    Wait-GpuFree -SceneName $name | Out-Null
    $run = Invoke-Scene -ScenePath $s.Scene -LogBase $logBase
    $total = Get-TotalCount -LogPath $run.Log -Kind $s.Kind
    $markers = Get-FailureMarkers -LogPath $run.Log -ErrPath $run.Err

    $pass = $false
    $reason = ''
    if ($null -eq $total) {
        $reason = "no RESULT/checks total line in log"
    } elseif ($total.Failures -ne 0) {
        $reason = ("printed failures: {0}" -f $total.Failures)
    } elseif ($total.Checks -ne $s.Expected) {
        $reason = ("checks {0} != expected {1}" -f $total.Checks, $s.Expected)
    } elseif ($markers.Count -gt 0) {
        $reason = ("failure markers: {0}" -f ($markers -join '; '))
    } elseif ($run.ExitCode -ne 0) {
        $reason = ("process exit code {0}" -f $run.ExitCode)
    } else {
        $pass = $true
        $reason = $total.Raw
    }

    $results += [PSCustomObject]@{
        Scene = $name; Expected = $s.Expected; Pass = $pass; Reason = $reason
    }
    if ($pass) {
        Write-Host ("  PASS  {0}" -f $reason) -ForegroundColor Green
    } else {
        Write-Host ("  FAIL  {0}" -f $reason) -ForegroundColor Red
    }
    Write-Host ""
}

if (-not $SkipMainSmoke) {
    Write-Host "--- main.tscn smoke (--quit-after $MainSmokeFrames, no count) ---"
    Wait-GpuFree -SceneName 'main.tscn' | Out-Null
    $run = Invoke-Scene -ScenePath 'res://scenes/main.tscn' -LogBase 'battery_main' -QuitAfter $MainSmokeFrames
    $markers = Get-FailureMarkers -LogPath $run.Log -ErrPath $run.Err
    $ready = Select-String -Path $run.Log -SimpleMatch -Pattern 'Universe ready' -ErrorAction SilentlyContinue
    $smokePass = ($markers.Count -eq 0) -and ($null -ne $ready)
    $smokeReason = if ($smokePass) { 'banner + no failure markers' } else {
        $bits = @()
        if (-not $ready) { $bits += 'no Universe-ready banner' }
        if ($markers.Count -gt 0) { $bits += ($markers -join '; ') }
        $bits -join '; '
    }
    $results += [PSCustomObject]@{
        Scene = 'main.tscn (smoke)'; Expected = 0; Pass = $smokePass; Reason = $smokeReason
    }
    if ($smokePass) {
        Write-Host ("  PASS  {0}" -f $smokeReason) -ForegroundColor Green
    } else {
        Write-Host ("  FAIL  {0}" -f $smokeReason) -ForegroundColor Red
    }
    Write-Host ""
}

# ---------------------------------------------------------------------------
# Summary table + exit code
# ---------------------------------------------------------------------------
Write-Host "=== Summary ===" -ForegroundColor Cyan
$results | ForEach-Object {
    $mark = if ($_.Pass) { 'PASS' } else { 'FAIL' }
    $color = if ($_.Pass) { 'Green' } else { 'Red' }
    Write-Host ("[{0}] {1,-28} expected={2,-4} {3}" -f $mark, $_.Scene, $_.Expected, $_.Reason) -ForegroundColor $color
}
$failed = @($results | Where-Object { -not $_.Pass })
Write-Host ("=== {0}/{1} scenes passed ===" -f ($results.Count - $failed.Count), $results.Count) -ForegroundColor Cyan
if ($failed.Count -gt 0) {
    Write-Host "[battery] EXIT 1 -- failing scenes:" -ForegroundColor Red
    $failed | ForEach-Object { Write-Host ("  {0}: {1}" -f $_.Scene, $_.Reason) -ForegroundColor Red }
    exit 1
}
Write-Host "[battery] EXIT 0 -- battery green" -ForegroundColor Green
exit 0
