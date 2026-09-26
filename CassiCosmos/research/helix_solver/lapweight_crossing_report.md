# Lap-Weight Degeneracy Crossing Curve — REPORT (U2)

**Date:** 2026-08-16 · **Pre-registration:** `lapweight_crossing_prereg.md`
(frozen before the run — the probe script was written after and never tuned to
the output). Every number below came verbatim from
`lapweight_crossing_probe.py` live output.

## Verdict (per the frozen tree): **CONTRADICTS**

The axial coefficient `az(s)` of the box family `h = (φ, 1, s)` has **exactly
one** sign change in `[0.5, 7.2361]`, at

```
s* = 2.268189     az(s*) = 8.05e-16
```

which lies **outside** the pre-registered success band
`[φ²·0.9, φ²·1.1] = [2.356231, 2.879837]` (it is ≈13.4% **below** the φ²·0.9
lower edge, i.e. ≈0.35 below φ² = 2.618). The director hypothesis U2 — that
the engine's default box aspect `(φ,1,φ²)` sits **at** the operator's critical
manifold — is therefore **not supported**: the marginal `s*` where the longest
axis flips from elliptic to anti-diffusive is a full step below the box aspect
the engine actually runs, not coincident with it.

## Anchor gate (calibration): **PASSED**

`lap_weights((φ,1,φ²))` reproduces the wave-8 tuple to the documented 3-decimal
precision for all six components (each `|diff| < 5e-4`):

| component | probe value | wave-8 target | \|diff\| |
|---|---|---|---|
| ax | 0.1273 | 0.127 | 3.22e-4 |
| ay | 0.7309 | 0.731 | 1.43e-4 |
| az | −0.0094 | −0.009 | 3.65e-4 |
| bxy | 0.0921 | 0.092 | 1.31e-4 |
| bxz | 0.0352 | 0.035 | 1.91e-4 |
| byz | 0.0424 | 0.042 | 4.41e-4 |

The formula used is the wave-8 `lap_weights` imported from `triaxial3d.py`
(reported by the probe as `formula source: imported from triaxial3d.py`); the
anchored negative `az ≈ −0.0094` confirms the documented anti-diffusive z-axis
at the default aspect.

## Trace table (verbatim from probe output)

```
s=  0.5000  az=+0.808555  ax=-0.008686  ay=+0.070601
s=  1.0000  az=+0.482405  ax=+0.013442  ay=+0.482405
s=  1.6180  az=+0.070390  ax=+0.070379  ay=+0.631470
s=  2.0000  az=+0.015932  ax=+0.096969  ay=+0.682405
s=  2.3562  az=-0.003233  ax=+0.116103  ay=+0.713985   (band lower edge)
s=  2.6180  az=-0.009365  ax=+0.127322  ay=+0.730857   (phi^2, the engine box)
s=  2.8798  az=-0.012256  ax=+0.136606  ay=+0.744003   (band upper edge)
s=  3.0000  az=-0.012938  ax=+0.140322  ay=+0.749071
s=  4.0000  az=-0.012523  ax=+0.161896  ay=+0.776522
s=  5.0000  az=-0.009780  ax=+0.173565  ay=+0.790097
s=  7.2360  az=-0.005521  ax=+0.185578  ay=+0.803244
```

`az(s)` is positive for small `s`, crosses **down** through zero once at
`s* = 2.2682`, and stays negative (anti-diffusive on the z-axis) for all larger
`s` in the scan range — including at the engine's default `s = φ² = 2.618`.

## Supplementary observations (NO verdict, per the frozen tree)

- **ax(s):** one crossing at `s = 0.868` — the `x`/`y` axis-coefficient swap
  region where the longest axis transitions from x to y (φ ↔ 1 scale), not a
  physics claim.
- **ay(s):** no crossing in the range (stays positive throughout here).
- These were reported with no verdict attached, exactly as pre-registered.

## Physical reading

The degeneracy model in the hypothesis is **qualitatively correct in shape but
quantitatively off-target**. The operator *does* have a critical manifold —
`az(s)` flips from elliptic (positive, `s < 2.268`) to anti-diffusive (negative,
`s > 2.268`) — so the family `(φ,1,s)` genuinely carries a marginal point where
the longest axis coasts. But that marginal point sits at `s* ≈ 2.268`, **not** at
φ² ≈ 2.618. The engine's default box `(φ,1,φ²)` therefore runs **well inside
the anti-diffusive regime** on the z-axis (az ≈ −0.0094 at the default), not at
the marginal point. If the box aspect is meant to be a derived degeneracy, the
measured `s*` is the operator-consistent value and the actual default is a
*choice* — the claimed "explained by the operator's degeneracy" unification is
**CONTRADICTED** by the frozen band. (This is a coefficient-manifold scan from
the wave-8 formula; it does not run the engine and does not modify any file.)

## Traceability

- Re-run from `CassiCosmos/`: `python research/helix_solver/lapweight_crossing_probe.py`
  (~2 s, deterministic, numpy).
- Files: `lapweight_crossing_prereg.md`, `lapweight_crossing_probe.py`,
  `lapweight_crossing_report.md` (all new, under `research/helix_solver/`).
- Formula: imported `triaxial3d.lap_weights` (wave-8, `triaxial3d.py:37-48`);
  anchor tuple from the wave-8 correction in `triaxial3d_report.md` and
  `triaxial3d_simop_corr_prereg.md`.
