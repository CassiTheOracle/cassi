# Live cloud–environment ledger receipt-integrity repeat — preregistration

Status: PRE-REGISTERED before the integrity repeat — 2026-09-02

## Reason for the repeat

The first execution under `rotation_tidal_ledger_prereg.md` completed all registered trajectories and merge states, but its raw JSON omitted the preregistered complete engine configuration and producer-source digest. Its physics replay is retained as a non-authoritative precheck, while the authoritative outcome is `INCONCLUSIVE—IMPLEMENTATION`.

This repeat tests the repaired receipt contract. It is not a tuned hypothesis retry: particle states, geometries, grids, timesteps, durations, field reset, group tags, equations, thresholds, and G86–G91 computations remain byte-for-byte or numerically identical to the original acquisition and verifier sources except for the added receipt metadata and integrity checks.

## Frozen integrity contract

The repeat runs the seven cases and one merge fixture specified in `rotation_tidal_ledger_prereg.md` exactly once. The raw receipt is `_diag/rotation_tidal_ledger_gpu_integrity.json`; the independent receipt is `_diag/rotation_tidal_ledger_verify_integrity.json`. The first unbound raw and verifier receipts remain at their original paths and must not be overwritten.

The new raw receipt must include:

- a SHA-256 digest of the acquisition source computed by the running Godot arm;
- the canonical field reset values;
- every explicitly passed engine configuration value for every case;
- effective extents, effective river `G_N`, and effective calibrated `G_eff` read from the configured engine; and
- every raw position, velocity, acceleration, and merge-spin array required by the original replay.

The Python verifier must reject a missing or mismatched producer digest, field reset, configuration key, effective value, case set, state count, or finite-state check before computing an authoritative physics verdict. Its receipt binds the raw JSON, acquisition source, verifier source, this preregistration, and the original preregistration by SHA-256.

## Frozen decisions

- Integrity checks fail: `INCONCLUSIVE—IMPLEMENTATION`; retain both runs and stop.
- Integrity checks pass: apply the unchanged G86–G91 gates and decision tree from `rotation_tidal_ledger_prereg.md`, retaining PASS and FAIL outcomes equally.

No geometry, threshold, duration, grid, timestep, field value, merge fixture, force branch, or normalization may change. Run the Godot arm once and the verifier once; do not rerun this integrity repeat.
