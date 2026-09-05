# CassiQwen L5c — Native Seeded Bridge Report

## Status: FAIL—2026-08-18

## Protocol result

`L5C-NATIVE-SEEDED-BRIDGE-PREREG.md` launched the native CassiCosmos scene successfully:

```text
[CassiQwenSeededMind] ready N=32 step=1 t=0.0050 port=7599
```

The sole L3 read-only observation was available and returned `step=1`, `t=0.005`, eight finite non-negative cells, and non-increasing $q$. Its highest cell had $q=0.19971212884439$.

## Failing criterion

The frozen protocol required the highest projected cell to be within one grid cell of $(20,10,26)$. The actual top cell has physical coordinates:

```text
x = 0.290322580645161
y = -0.354838709677419
z = 0.677419354838710
```

The criterion failed. The managed sidecar was stopped; there was no retry.

## Why the criterion was invalid

The engine documents its projection coordinates as the vertex map:

```text
physical = (2 * g / (N - 1) - 1) * extent
```

For $N=32$, the observed coordinates map exactly to grid indices $(20,10,26)$. The L5c test harness incorrectly tested against cell-center coordinates; it did not retain `gx`, `gy`, and `gz` because the L3 adapter intentionally projected only physical coordinates.

This explains the failed check but does not reverse the terminal L5c verdict.

## Terminal verdict

**FAIL.** The failure is a projection-coordinate calibration defect in the L5c consumer check, not evidence that the field seed or live bridge failed.

## Successor boundary

A new protocol may reuse the fixed seed and native scene while changing only the consumer acceptance calculation to invert the documented vertex map:

\[
g = \operatorname{round}\left(\frac{(x / extent)+1}{2}(N-1)\right).
\]

It must make one launch and one observation. It must not alter the engine, seed, steps, bridge commands, or Qwen path.
