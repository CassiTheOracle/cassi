# CassiQwen L14 — Local Candidate-Pool Coupling Probe Pre-registration

## Status: FROZEN BEFORE IMPLEMENTATION—2026-08-18

## Provenance

L11c found no aligned-versus-shuffled effect because its relation relays were distant from the measured candidate pools. L14 changes only the spatial scale: it uses two candidate pools placed on neighboring interior grid anchors with a relay at their midpoint. The PDE, deposit width, step count, readout definition, and control logic are otherwise fixed.

This is a mechanism probe, not an action-quality or Qwen experiment.

## Fixed geometry

Use the existing unchanged two-fluid engine with `N=32`, bridge disabled, and one local RenderingDevice.

- answer pool center: $(x,y,z)=(-0.125,0,0)$;
- retrieve pool center: $(+0.125,0,0)$;
- aligned relay: $(0,0,0)$;
- shuffled relay: $(0,0,+0.75)$;
- candidate and relay scatter width: $σ=0.5$;
- PDE steps: 16;
- candidate-local readout: the exact anchor cell plus its six axis neighbors, avoiding a large window that swallows both pools.

Candidate channels use the fixed L9 features from the L11 probe. Relay channels are fixed at `(cy,ci)=(0.62,0.05)` and `(0.05,0.62)`.

## Arms

1. `off`: candidates only, zero PDE steps.
2. `aligned`: candidates plus both relays at the midpoint, 16 steps.
3. `shuffled`: candidates plus both relays at the distant shuffled point, 16 steps.
4. `swapped`: candidates plus midpoint relays with Yang/Yin amplitudes exchanged, 16 steps.

## Acceptance and decision tree

Record finite/bounded states, candidate-local $q$, and answer-minus-retrieve difference.

1. Setup/readback/non-finite failure: `INVALID`.
2. If aligned and shuffled differences are equal within $10^{-9}$: `NULL`.
3. If aligned differs from shuffled but equals swapped within $10^{-9}$: `NULL`.
4. If aligned differs from both controls: `MECHANISM-DIFFERENCE`.

No parameter sweep, extra steps, retries, Qwen request, or engine/shader modification. One windowed launch runs all arms and writes one receipt.
