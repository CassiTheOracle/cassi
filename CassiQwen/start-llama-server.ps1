[CmdletBinding()]
param(
    # Offline teacher/baseline launcher only. The field-only terminal and
    # port-8086 provider never invoke this script or load its native runtime.
    [ValidateRange(1024, 262144)]
[int] $ContextSize = 16384,

    [ValidateRange(0, 99)]
    [int] $GpuLayers = 40,

    [ValidateRange(1, 65535)]
    [int] $Port = 8084,

    [ValidateRange(1, 32)]
    [int] $ParallelSlots = 1,

    [string] $SlotSavePath = '_diag\native-slots',

    [string] $ServerPath = 'native\llama.cpp\build-cassi\bin\Release\llama-server.exe',

    # Retained for compatibility with older documented invocations. Modal is now default-on.
    [switch] $CassiModal,

    [switch] $NoCassiModal,

    [ValidateRange(0.0, 1.0)]
    [double] $CassiModalRetained = 0.9,

    [ValidateRange(0.000001, 1000000.0)]
    [double] $CassiModalPhi = 1.61803398875,

    [ValidateRange(0.000001, 1000000.0)]
    [double] $CassiModalDt = 0.005,

    [ValidateRange(0.000001, 1000000.0)]
    [double] $CassiModalOmega2 = 20.0,

    [ValidateRange(0.000001, 1000000.0)]
    [double] $CassiModalCoupling = 1.0,

    [ValidateRange(1, 1024)]
    [int] $CassiModalStepsPerLayer = 4,

    [ValidateRange(0, 99)]
    [int] $CassiQiFieldLayer = 32,

    [ValidateRange(1, 4)]
    [int] $CassiQiFieldScales = 4,

    [switch] $NoCassiQiField
)

$ErrorActionPreference = 'Stop'

$root = $PSScriptRoot
$server = Join-Path $root $ServerPath
$model = Join-Path $root 'Qwen3.8-27B-Q4_K_M.gguf'

foreach ($path in @($server, $model)) {
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
        throw "Required CassiQwen artifact is missing: $path"
    }
}
$slotDirectory = Join-Path $root $SlotSavePath
New-Item -ItemType Directory -Force -Path $slotDirectory | Out-Null

$arguments = @(
    '--model', $model,
    '--host', '127.0.0.1',
    '--port', "$Port",
    '--ctx-size', "$ContextSize",
    '--parallel', "$ParallelSlots",
    '--gpu-layers', "$GpuLayers",
    '--batch-size', '512',
    '--ubatch-size', '512',
    '--slot-save-path', $slotDirectory,
    '--metrics'
)

if (-not $NoCassiQiField) {
    $arguments += @(
        '--cassi-qi-field',
        '--cassi-qi-field-layer', "$CassiQiFieldLayer",
        '--cassi-qi-field-scales', "$CassiQiFieldScales"
    )
}

& $server @arguments

exit $LASTEXITCODE

