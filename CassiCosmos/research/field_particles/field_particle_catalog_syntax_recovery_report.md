# Field-Particle Catalog Syntax Recovery Result

## Status: PASS—September 2, 2026

## 1. Registered run

The syntax-only recovery added the three frozen type annotations. The clean
windowed Godot arm parsed, completed 55 checks with zero failures, and exited 0
in 21.7 seconds. The stationary GPU evolution took 757 ms and the boosted
evolution took 484 ms.

## 2. Catalog measurements

The pinned seed, stationary final state, boosted initial state, and boosted
final state each resolved to one derived object. The exact and evolved vacuum
states resolved to zero objects.

The two-Gaussian readout control resolved to two objects on opposite sides of
the selected axis. Its catalog charge was `1.014842882283`; direct integration
of the canonical carrier density gave `1.014842885598`, a relative difference
of `3.27e-9`.

Repeated reads and clear/reconstruct cycles were byte-identical. Retaining or
reconstructing the catalog before the control step produced canonical states
with zero differing bytes, so catalog state does not feed back into field
evolution.

## 3. Retained dynamics evidence

All prior gates passed in the same run: exact import and zero-time identity,
stationary charge/localization/energy bounds, phase rate, temporal-gauge Gauss
residual, vacuum residual, boosted motion and charge retention, zero legacy
particle dispatches, and the independent NumPy energy/gradient reconstruction.

## 4. Verdict

**PASS—FIELD-PARTICLE CATALOG SYNTAX RECOVERY.**

The canonical state remains the field. Particle objects are deterministic,
reconstructible observables derived from carrier-density cores and their raw
field tails.
