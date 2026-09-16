#!/usr/bin/env bash
# Registered multi-IC attractor arms (research/matter_formation/trajectory_general_attractor_prereg.md §3).
# Windowed runs only; one Godot instance at a time. Run from the repository root:
#   bash research/matter_formation/run_trajectory_attractor_arms.sh
set -u
EXE="${GODOT_EXE:-C:/Users/Carina/AppData/Local/Microsoft/WinGet/Packages/GodotEngine.GodotEngine.Mono_Microsoft.Winget.Source_8wekyb3d8bbwe/Godot_v4.7.1-stable_mono_win64/Godot_v4.7.1-stable_mono_win64_console.exe}"
ICS=(2 3 5 7 8 10 11 6)
mkdir -p _diag/matter_formation
for IC in "${ICS[@]}"; do
  LOG="_diag/matter_formation/attractor_ic${IC}.log"
  echo "=== attractor arm ic=${IC} start $(date +%H:%M:%S) ==="
  "$EXE" --path . res://scenes/verify_trajectory_probe.tscn -- \
    --mode=shell --recorder=on --ic="${IC}" --arrangement=0 --motion=1 \
    --gridless=on --gravity=5 --field-attractor-init=on \
    --particles=8192 --tracers=4096 --sample-stride=4096 --sample-capacity=256 \
    --event-capacity=65536 --merge-cadence=64 --dt=0.001 --steps=1000000 \
    --batch-steps=64 --batches-per-frame=8 --timeout-sec=1800 \
    --out-dir="res://_diag/matter_formation/attractor_ic${IC}" \
    >"$LOG" 2>&1
  RC=$?
  tail -4 "$LOG"
  echo "=== attractor arm ic=${IC} done rc=${RC} $(date +%H:%M:%S) ==="
  if [ "$RC" -ne 0 ]; then
    echo "=== aborting remaining arms after arm rc=${RC} ==="
    exit "$RC"
  fi
done
echo "=== all attractor arms complete $(date +%H:%M:%S) ==="
