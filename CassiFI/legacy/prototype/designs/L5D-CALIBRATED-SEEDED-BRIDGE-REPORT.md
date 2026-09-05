# CassiQwen L5d — Calibrated Seeded Bridge Report

## Status: PASS—2026-08-18

## Protocol

This report executes the frozen `L5D-CALIBRATED-SEEDED-BRIDGE-PREREG.md`. It reuses the native scene, fixed seed, one PDE step, loopback-only service, and read-only L3 observation from L5c. Its only changed criterion is the documented vertex-coordinate inverse.

## Startup and observation

The windowed native scene reached readiness:

```text
[CassiQwenSeededMind] ready N=32 step=1 t=0.0050 port=7599
```

The one L3 observation returned:

| Measurement | Value |
|---|---:|
| Step | 1 |
| Time | 0.005 |
| Mean Yang field | 0.0000444396992856968 |
| Mean Yin field | 0.0000274658193118039 |
| Maximum imbalance squared | $6.2949523433086\times10^{-11}$ |
| Projection cells | 8 |
| Highest $q$ | 0.19971212884439 |
| Lowest returned $q$ | 0.00261457884843892 |

All eight cells were finite, had non-negative $q$, and were ordered non-increasingly by $q$.

## Geometry calibration

The highest projected physical coordinate was:

\[
(x,y,z)=(0.290322580645161,-0.354838709677419,0.677419354838710).
\]

Applying the source-defined inverse vertex map with $N=32$:

\[
g(p)=\operatorname{round}\left(\frac{p+1}{2}\cdot31\right)
\]

produces exactly:

\[
(g_x,g_y,g_z)=(20,10,26).
\]

This is the fixed seed’s expected TSC anchor.

## Terminal verdict

**PASS.** CassiQwen now has a reproducible live receipt for a nonzero, finite, bounded field projection with calibrated geometry. The managed Godot sidecar was stopped after the one required read-only observation.

## Interpretation

- **T1 measured:** field startup, state, eight-cell projection, $q$ ordering, and coordinate inversion above.
- **T2 inferred:** the top-$q$ projection is now a deterministic bounded signal that can be passed into a future CassiQwen shadow evaluator.
- **T3 speculative:** that any mapping from this signal to retrieved evidence improves a Qwen task. No Qwen call occurred in this protocol.

## Next gated step

The next protocol should be a fully offline signal-mapping verification: map fixed candidate IDs to the eight projection ranks, prove exact default-off identity and deterministic permutation behavior, and only then couple that mapping to the frozen L2 question board.
