#!/usr/bin/env bash
# App-fidelity arms (research/matter_formation/trajectory_general_attractor_prereg.md §5).
# Reproduces scenes/main.tscn's macro initial condition (three ring-separated blobs at
# cluster_radius 120 / separation 1500, the scene's dt and force-refresh cadence) with
# 8192 particles. Windowed runs only, one Godot instance at a time.
# Run from the repository root:
#   bash research/matter_formation/run_trajectory_app_fidelity_arms.sh [A3 C1 ...]
set -u
EXE="${GODOT_EXE:-C:/Users/Carina/AppData/Local/Microsoft/WinGet/Packages/GodotEngine.GodotEngine.Mono_Microsoft.Winget.Source_8wekyb3d8bbwe/Godot_v4.7.1-stable_mono_win64/Godot_v4.7.1-stable_mono_win64_console.exe}"
ARMS=("$@")
if [ "${#ARMS[@]}" -eq 0 ]; then
  ARMS=(A3 C1 C2 A6 L3)
fi
COMMON=(--mode=shell --recorder=on --arrangement=0 --motion=1
  --gridless=on --gravity=5 --field-attractor-init=on
  --particles=8192 --tracers=4096 --sample-stride=400 --sample-capacity=256
  --event-capacity=65536 --dt=0.05 --steps=100000 --batch-steps=2
  --batches-per-frame=8 --timeout-sec=1800
  --cluster-radius=120 --radius-fraction=1.0 --total-mass=2320000 --tree-cadence=250)
mkdir -p _diag/matter_formation/attractor_app
arm_args() {
  case "$1" in
    A3) echo "--ic=3 --clusters=3 --separation=1500 --box-scale=9.70 --freeze-field=on" ;;
    A6) echo "--ic=6 --clusters=3 --separation=1500 --box-scale=9.70 --freeze-field=on" ;;
    C1) echo "--ic=3 --clusters=1 --separation=0 --box-scale=0.78 --freeze-field=on" ;;
    C2) echo "--ic=3 --clusters=1 --separation=0 --box-scale=9.70 --freeze-field=on" ;;
    L3) echo "--ic=3 --clusters=3 --separation=1500 --box-scale=9.70 --freeze-field=off" ;;
    *) echo "" ;;
  esac
}
for ARM in "${ARMS[@]}"; do
  EXTRA="$(arm_args "$ARM")"
  if [ -z "$EXTRA" ]; then
    echo "=== unknown app-fidelity arm '${ARM}' — skipped ==="
    continue
  fi
  LOG="_diag/matter_formation/attractor_app/${ARM}.log"
  echo "=== app-fidelity arm ${ARM} start $(date +%H:%M:%S) ==="
  # shellcheck disable=SC2086
  "$EXE" --path . res://scenes/verify_trajectory_probe.tscn -- \
    "${COMMON[@]}" $EXTRA \
    --out-dir="res://_diag/matter_formation/attractor_app/${ARM}" \
    >"$LOG" 2>&1
  RC=$?
  tail -4 "$LOG"
  echo "=== app-fidelity arm ${ARM} done rc=${RC} $(date +%H:%M:%S) ==="
  if [ "$RC" -ne 0 ]; then
    echo "=== aborting remaining arms after arm rc=${RC} ==="
    exit "$RC"
  fi
done
echo "=== app-fidelity arms complete $(date +%H:%M:%S) ==="
