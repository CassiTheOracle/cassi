#!/usr/bin/env bash
# Fresh serial morphology-operator worlds defined by the bound V1 protocol.
set -euo pipefail

EXE="${GODOT_EXE:-C:/Users/Carina/AppData/Local/Microsoft/WinGet/Packages/GodotEngine.GodotEngine.Mono_Microsoft.Winget.Source_8wekyb3d8bbwe/Godot_v4.7.1-stable_mono_win64/Godot_v4.7.1-stable_mono_win64_console.exe}"
ROOT="_diag/matter_formation/morphology_operator_v1_20260919"
COMMON=(--mode=shell --recorder=on --arrangement=0 --motion=1 --gridless=on --gravity=5
  --field-attractor-init=on --river-calibrate-gn=on --particles=8192 --tracers=4096
  --sample-stride=400 --sample-capacity=256 --event-capacity=65536 --dt=0.05
  --steps=100000 --batch-steps=2 --batches-per-frame=8 --timeout-sec=1800 --tree-cadence=250)

arm_args() {
  case "$1" in
    MH3) echo "--seed=20261011 --ic=3 --clusters=3 --cluster-radius=100 --separation=1250 --box-scale=8.0833 --total-mass=1600000 --radius-fraction=1.0 --freeze-field=on" ;;
    MH6) echo "--seed=20261012 --ic=6 --clusters=3 --cluster-radius=180 --separation=2250 --box-scale=14.5500 --total-mass=8017920 --radius-fraction=1.0 --freeze-field=on" ;;
    MHC3) echo "--seed=20261013 --ic=3 --clusters=1 --cluster-radius=144 --separation=0 --box-scale=11.6400 --total-mass=4008960 --radius-fraction=1.0 --freeze-field=on" ;;
    MHL3) echo "--seed=20261014 --ic=3 --clusters=3 --cluster-radius=144 --separation=1800 --box-scale=11.6400 --total-mass=4008960 --radius-fraction=1.0 --freeze-field=off" ;;
    *) return 1 ;;
  esac
}

mkdir -p "$ROOT"
for arm in MH3 MH6 MHC3 MHL3; do
  if [ -e "$ROOT/$arm/receipt.json" ]; then
    echo "refusing to overwrite morphology holdout: $ROOT/$arm" >&2
    exit 2
  fi
  extra="$(arm_args "$arm")"
  log="$ROOT/$arm.log"
  echo "=== morphology-operator holdout $arm start $(date -u +%FT%TZ) ==="
  # shellcheck disable=SC2086
  "$EXE" --path . res://scenes/verify_trajectory_probe.tscn -- \
    "${COMMON[@]}" $extra --out-dir="res://$ROOT/$arm" >"$log" 2>&1
  python tools/analyze_trajectory_attractor.py --allow-unregistered \
    --run "$ROOT/$arm" --out "$ROOT/${arm}_metadata.json" >>"$log" 2>&1
  echo "=== morphology-operator holdout $arm complete $(date -u +%FT%TZ) ==="
done
