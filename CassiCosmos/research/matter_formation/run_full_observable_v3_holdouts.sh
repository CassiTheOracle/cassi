#!/usr/bin/env bash
# Fresh clean-GPU full-observable holdouts frozen by
# research/equation_discovery/full_observable_operator_v3_prereg.md.
# Run from CassiCosmos. Local-RD scenes are windowed and strictly serial.
set -euo pipefail

EXE="${GODOT_EXE:-C:/Users/Carina/AppData/Local/Microsoft/WinGet/Packages/GodotEngine.GodotEngine.Mono_Microsoft.Winget.Source_8wekyb3d8bbwe/Godot_v4.7.1-stable_mono_win64/Godot_v4.7.1-stable_mono_win64_console.exe}"
ROOT="_diag/matter_formation/full_observable_v3_20260919"
COMMON=(--mode=shell --recorder=on --arrangement=0 --motion=1 --gridless=on --gravity=5
  --field-attractor-init=on --river-calibrate-gn=on --particles=8192 --tracers=4096
  --sample-stride=400 --sample-capacity=256 --event-capacity=65536 --dt=0.05
  --steps=100000 --batch-steps=2 --batches-per-frame=8 --timeout-sec=1800 --tree-cadence=250)

arm_args() {
  case "$1" in
    CH3) echo "--seed=20260925 --ic=3 --clusters=3 --cluster-radius=90 --separation=1125 --box-scale=7.275 --total-mass=1160000 --radius-fraction=1.0 --freeze-field=on" ;;
    CH6) echo "--seed=20260926 --ic=6 --clusters=3 --cluster-radius=150 --separation=1875 --box-scale=12.125 --total-mass=4640000 --radius-fraction=1.0 --freeze-field=on" ;;
    CHC3) echo "--seed=20260927 --ic=3 --clusters=1 --cluster-radius=120 --separation=0 --box-scale=9.70 --total-mass=2320000 --radius-fraction=1.0 --freeze-field=on" ;;
    CHL3) echo "--seed=20260928 --ic=3 --clusters=3 --cluster-radius=120 --separation=1500 --box-scale=9.70 --total-mass=2320000 --radius-fraction=1.0 --freeze-field=off" ;;
    *) return 1 ;;
  esac
}

mkdir -p "$ROOT"
for arm in CH3 CH6 CHC3 CHL3; do
  if [ -e "$ROOT/$arm/receipt.json" ]; then
    echo "refusing to overwrite frozen holdout: $ROOT/$arm"
    exit 2
  fi
  extra="$(arm_args "$arm")"
  log="$ROOT/$arm.log"
  echo "=== full-observable v3 holdout $arm start $(date -u +%FT%TZ) ==="
  # shellcheck disable=SC2086
  "$EXE" --path . res://scenes/verify_trajectory_probe.tscn -- \
    "${COMMON[@]}" $extra --out-dir="res://$ROOT/$arm" >"$log" 2>&1
  python tools/analyze_trajectory_attractor.py --allow-unregistered \
    --run "$ROOT/$arm" --out "$ROOT/${arm}_metadata.json" >>"$log" 2>&1
  echo "=== full-observable v3 holdout $arm complete $(date -u +%FT%TZ) ==="
done
