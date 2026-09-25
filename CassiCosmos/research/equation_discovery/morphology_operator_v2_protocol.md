# Morphology-Aware Field Operator Campaign V2

## Status: Ready — 2026-09-20

## Purpose

V2 executes the same target-independent 37-atom morphology language and the same four fresh trajectory worlds declared in `morphology_operator_v1_protocol.md`, using a bounded field-selection schedule that remains within the resident regional field's observation capacity.

V1 produced no receipt and no hidden-target result. Its root field faulted during the final synthesis registration after twelve completed development-only selections. The failure is recorded in the V1 protocol. V2 starts a new field instance and does not reuse that faulted state.

## Language and selection surface

The recorded snapshot alphabet is unchanged: 31 V4 atoms plus compactness, normalized radial spread, anisotropy, planarity, shell tangentiality, and radial counterflow. All coordinates use only current position, velocity, and mass.

The regional field permits 256 target-independent observations in one resident selection session. V2 has six seed decisions, six mutation decisions, and one synthesis decision, so it uses 16 candidates per local decision: ten dynamic baseline coordinates (`one`, `q`, `speed`, `radial_speed`, `transverse_speed`, `field_energy`, `local_density`, `enclosed_mass`, `divergence`, `shear`) plus all six morphology coordinates. The mutation decision uses `q`, `field_energy`, compactness, and radial spread. Each morphology coordinate remains directly selectable in every vector frame.

The six frames, typed operations, 60/40 chronological development split, development worlds, target-ban, hidden-target chronology, classification thresholds, receipt self-check, and mutation controls are unchanged from V1. The V2 executor binds itself, the V2 protocol, V4 predecessor receipt, full morphology implementation, development files, and the four already-created fresh trajectory files.

## Fresh holdouts

The four trajectory files in `CassiCosmos/_diag/matter_formation/morphology_operator_v1_20260919/` are carried forward unchanged: `MH3`, `MH6`, `MHC3`, and `MHL3`. Their accelerations have not been supplied to a successful field selection. V2 may read their targets only after its new field instance commits the selected synthesis expression.

## Preflight and invocation

`python CassiFI/run_cassi_morphology_operator_invention.py --home CassiFI/_diag/morphology-operator-v2-organism --workspace . --preflight` must pass before the single V2 receipt invocation. It validates inherited scalar/frame controls, deterministic feature replay, positive development-target energy, morphology firing controls, the full 37-atom snapshot alphabet, and the 16-candidate seed/mutation ceiling.

The output path is `CassiFI/_diag/morphology-operator-v2/receipt.json`; the launcher refuses overwrite. Independent verification reconstructs the entire construction and hidden target comparison from the committed receipt.
