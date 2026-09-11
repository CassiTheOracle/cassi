#!/usr/bin/env bash
# Registered Gaussian energy/seed arms.
# Protocol: trajectory_energy_prereg.md. Run from the CassiCosmos repository root.
# GPU scenes are windowed and run one at a time.
set -u

EXE="${GODOT_EXE:-C:/Users/Carina/AppData/Local/Microsoft/WinGet/Packages/GodotEngine.GodotEngine.Mono_Microsoft.Winget.Source_8wekyb3d8bbwe/Godot_v4.7.1-stable_mono_win64/Godot_v4.7.1-stable_mono_win64_console.exe}"
SEEDS=(20260910 20260911)
SPEEDS=(0.0 0.5 1.0 2.0)
mkdir -p _diag/matter_formation

for SEED in "${SEEDS[@]}"; do
  for SPEED in "${SPEEDS[@]}"; do
    LABEL="s${SEED}_v${SPEED/./p}"
    OUT="res://_diag/matter_formation/energy_gaussian_${LABEL}"
    LOG="_diag/matter_formation/energy_gaussian_${LABEL}.log"
    echo "=== energy arm seed=${SEED} speed=${SPEED} start $(date +%H:%M:%S) ==="
    "$EXE" --path . res://scenes/verify_trajectory_probe.tscn -- \
      --mode=shell --recorder=on --seed="${SEED}" --ic=1 --arrangement=2 \
      --motion=4 --speed="${SPEED}" --gravity=5 --gridless=on \
      --field-attractor-init=on --freeze-field=on --river-calibrate-gn=off \
      --particles=8192 --tracers=4096 --sample-stride=400 --sample-capacity=256 \
      --event-capacity=65536 --merge-cadence=64 --dt=0.001 --steps=100000 \
      --batch-steps=64 --batches-per-frame=8 --tree-cadence=1 --timeout-sec=900 \
      --out-dir="${OUT}" >"${LOG}" 2>&1
    RC=$?
    tail -4 "${LOG}"
    echo "=== energy arm seed=${SEED} speed=${SPEED} done rc=${RC} $(date +%H:%M:%S) ==="
    if [ "${RC}" -ne 0 ]; then
      echo "=== aborting remaining energy arms after rc=${RC} ==="
      exit "${RC}"
    fi
  done
done

echo "=== all energy arms complete $(date +%H:%M:%S) ==="
