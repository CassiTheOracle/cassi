# Interactive Field Workbench: Next-Frontier Report

## Status: Implemented and measured—2026-08-18

## Verdict

The interactive workbench frontier is **ADOPT** for paused, inline, periodic-grid experiments. The focused verifier completed **18/18 checks**, and the pre-existing workbench verifier completed **12/12 checks**.

The runtime now exposes one coherent workbench surface:

- an explicitly armed world-space viewport cursor with a visible marker;
- numeric and viewport placement through the same cursor API;
- validated, ordered deposit, channel-alignment, and particle-impulse operations;
- deterministic scenario save/replay with checksums;
- exact controlled-mode checkpoints and branch restore;
- fixed-scale numerical branch differences;
- deterministic shell, Gaussian-knot, filament, vortex, and finite-$\varphi$-cascade recipes;
- a guided equal-field-intensity/different-coherence scenario;
- explicit rejection for live, decoupled, and boxless/site-owned mutation.

## Measurements

The guided scenario held field intensity equal to the reported precision:

|Region|Mean $E^2$|Mean $q_{\mathrm{coh}}$|Mean $\epsilon$|
|---|---:|---:|---:|
|$\varphi$-aligned|3.9999997503|0.9520123565|$4.02\times10^{-8}$|
|orthogonal|3.9999997503|0.0276433885|−3.8042259465|

The coherence gap is approximately **0.92437** while the field-intensity relative difference is **0** at the fixture's precision. This establishes the intended presentation claim: equal $E_Y^2+E_I^2$ does not imply equal bounded coherence. It is not presented as a total Hamiltonian-energy measurement.

The controlled branch fixture reproduced its no-operation sibling digest exactly and produced a distinct digest plus explicit deltas for a deposited branch. Checkpoint restore returned every captured buffer to the baseline digest and restored the recorded step/time seam.

## GPU promotion verdict

Two bounded GPU kernels were implemented and independently compiled:

- `compute/cassi_workbench_field.glsl`: norm-preserving channel alignment with zero-strength identity and antipodal guard;
- `compute/cassi_workbench_particle.glsl`: periodic bounded particle impulse.

The production host keeps all three operations on the measured CPU reference backend in this landing. The attempted host integration exposed concurrent corruption in the owner-live `cassi_sim.gd`; it was removed and rebuilt from the tracked clean source rather than risking a damaged simulator. The shader kernels remain registered in `scripts/contracts/layout.gd` and are ready for a dedicated, separately verified host-integration wave.

Normalized deposit remains CPU by the frozen decision tree. A non-normalized one-pass GPU substitute was not accepted. Its correct promotion requires deterministic reduction of radial weights and must beat one full 64³ readback without changing the command's total-amount semantics.

## Operational limits

Checkpoint and branch restore reject:

- decoupled physics ownership;
- boxless/site topology;
- meshless mode;
- particle merging;
- black-hole evolution;
- tracking envelope and home-window tracking.

Those modes contain authoritative state beyond the six captured buffers. Rejecting them is deliberate; the workbench does not claim an exact branch while omitting hidden state.

The existing field-slice renderer remains outside this frontier, so branch comparison is numerical rather than a difference texture. The UI names field intensity, bounded coherence, and disequilibrium separately to prevent `field_q` from being mistaken for $q_{\mathrm{coh}}$.

## Verification commands

Run windowed from the CassiCosmos repository root:

```text
Godot_v4.7.1-stable_mono_win64_console.exe --path . res://scenes/verify_workbench_frontier.tscn
Godot_v4.7.1-stable_mono_win64_console.exe --path . res://scenes/verify_field_workbench.tscn
```

Observed results:

- next-frontier verifier: **18 checks, 0 failures**;
- existing workbench regression: **12 checks, 0 failures**;
- each new workbench compute shader compiled separately with `glslangValidator` after stripping Godot's `#[compute]` import directive.

The verifier process still prints pre-existing shader-extension capability notices and nine leaked shader RIDs during teardown. Those warnings occur after the green verdict and originate in the broader simulator lifecycle, not the workbench command path.
