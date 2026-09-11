#!/usr/bin/env bash
# Calibrated scene-fidelity follow-up registered in
# research/matter_formation/trajectory_general_attractor_prereg.md §7.
# Windowed local-RD runs only; one Godot instance at a time.
# Run from the repository root:
#   bash research/matter_formation/run_trajectory_scene_calibrated_arms.sh [G3 GC1 ...]
set -u
EXE="${GODOT_EXE:-C:/Users/Carina/AppData/Local/Microsoft/WinGet/Packages/GodotEngine.GodotEngine.Mono_Microsoft.Winget.Source_8wekyb3d8bbwe/Godot_v4.7.1-stable_mono_win64/Godot_v4.7.1-stable_mono_win64_console.exe}"
ARMS=("$@")
if [ "${#ARMS[@]}" -eq 0 ]; then
  ARMS=(G3 G6 GC1 GC2 GL3)
fi
COMMON=(--mode=shell --recorder=on --arrangement=0 --motion=1
  --gridless=on --gravity=5 --field-attractor-init=on
  --river-calibrate-gn=on
  --particles=8192 --tracers=4096 --sample-stride=400 --sample-capacity=256
  --event-capacity=65536 --dt=0.05 --steps=100000 --batch-steps=2
  --batches-per-frame=8 --timeout-sec=1800
  --cluster-radius=120 --radius-fraction=1.0 --total-mass=2320000 --tree-cadence=250)
ROOT="_diag/matter_formation/attractor_scene_calibrated"
mkdir -p "$ROOT"
arm_args() {
  case "$1" in
    G3) echo "--ic=3 --clusters=3 --separation=1500 --box-scale=9.70 --freeze-field=on" ;;
    G6) echo "--ic=6 --clusters=3 --separation=1500 --box-scale=9.70 --freeze-field=on" ;;
    GC1) echo "--ic=3 --clusters=1 --separation=0 --box-scale=0.78 --freeze-field=on" ;;
    GC2) echo "--ic=3 --clusters=1 --separation=0 --box-scale=9.70 --freeze-field=on" ;;
    GL3) echo "--ic=3 --clusters=3 --separation=1500 --box-scale=9.70 --freeze-field=off" ;;
    *) echo "" ;;
  esac
}
for ARM in "${ARMS[@]}"; do
  EXTRA="$(arm_args "$ARM")"
  if [ -z "$EXTRA" ]; then
    echo "=== unknown calibrated scene arm '${ARM}' — skipped ==="
    continue
  fi
  LOG="$ROOT/${ARM}.log"
  echo "=== calibrated scene arm ${ARM} start $(date +%H:%M:%S) ==="
  # shellcheck disable=SC2086
  "$EXE" --path . res://scenes/verify_trajectory_probe.tscn -- \
    "${COMMON[@]}" $EXTRA \
    --out-dir="res://$ROOT/${ARM}" \
    >"$LOG" 2>&1
  RC=$?
  tail -4 "$LOG"
  echo "=== calibrated scene arm ${ARM} done rc=${RC} $(date +%H:%M:%S) ==="
  if [ "$RC" -ne 0 ]; then
    echo "=== aborting remaining calibrated scene arms after arm rc=${RC} ==="
    exit "$RC"
  fi
done
echo "=== calibrated scene arms complete $(date +%H:%M:%S) ==="
