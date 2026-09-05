# CassiQwen L5d — Calibrated Seeded Bridge Pre-registration

## Status: FROZEN BEFORE RUN—2026-08-18

## Provenance and single change

`L5C-NATIVE-SEEDED-BRIDGE-REPORT.md` is terminal `FAIL` because its consumer-side coordinate check used a cell-center map. The source-defined projection uses the vertex map $x=(2g/(N-1)-1)\,extent$.

This successor changes only the acceptance calculation: derive the candidate grid index from the returned physical coordinate using the documented inverse vertex map. The native scene, fixed seed, grid, one PDE step, loopback service, adapter, and one-observation stop rule are unchanged.

## Fixed run

Launch `CassiCosmos/scenes/cassi_qwen_seeded_mind.tscn` once in windowed Godot. Observe once via:

```js
observeCassiField({ enabled: true, host: '127.0.0.1', port: 7599, projectionK: 8 })
```

No Qwen request and no external bridge mutation command is permitted.

## Fixed acceptance calculation

For each top-cell physical coordinate $p \in [-1,1]$ and $N=32$, compute:

\[
g(p)=\operatorname{round}\left(\frac{p+1}{2}(N-1)\right).
\]

The first returned projection cell must map to $(g_x,g_y,g_z)=(20,10,26)$ exactly. The remaining fixed checks are: available result, `step=1`, $|t-0.005|\le10^{-9}$, eight finite cells, non-negative $q$, first $q>0$, and non-increasing $q$.

## Decision and stopping tree

- Launch, adapter, state, geometry, ordering, or finite-value failure: `FAIL`.
- Every criterion passes: `PASS`.

Exactly one launch, one observation, one managed stop. No retry, parameter change, alternate seed, extra step, or Qwen call.
