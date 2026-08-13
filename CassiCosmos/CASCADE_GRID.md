# CASCADE_GRID — A φ-Theoretic Grid Method for the Cassi Space Sim

**Status:** Design + measurements (shader-exact NumPy chain; no sim code changed this turn)
**Repo:** `godot/space-sim` (the cassi-toe theory repo is read-only input)
**Date:** 2026-08-12

---

## 0. The problem, restated

The gravity simulation now forms a bubble-lattice-like structure in layers across
the sim space — the triaxial lattice the theory expects. The remaining defect is
the one you saw: **the 3D grid biases the bubbles to the wrong places.** The
φ-aspect box (GRID_LAYOUT.md) removed the box-scale straight-line lock, but two
grid artifacts remain at the bubble scale:

1. **Placement (phase) bias** — the force on a particle depends on where the
   source and the particle sit *within* a cell. Density accumulates at preferred
   cell phases, so bubbles condense at grid-pinned positions instead of where the
   dynamics wants them.
2. **Scale quantization** — everything that forms is resolved at one scale band
   (a few cells of the single grid). A cascade has bubbles at many rungs; the
   single grid only lets one rung form cleanly.

This design addresses both with one method — the **cascade grid** — and answers
the multi-scale question with measurements.

---

## 1. Measurement protocol (what was actually measured)

All numbers below come from a shader-exact NumPy replica of the live chain
(`deposit(TSC) → fftn → Φ̂ = −ρ̂/k² (k=0 nulled) → ifftn → periodic central
difference → trilinear probe`), L = 75, N = 64, source = TSC blob at f = (0.5,
0.5, 0.5) — the sim's real deposit class.

- **Validation:** the 4h ring ratio reproduces the skill-pinned shader value
  exactly (**1.0896**), and the delta-source excess (2.05× at 4h) matches the
  pinned "1.9×@4h" statement. The chain is shader-exact.
- **The k-factor trap (documented for the implementation turn):** `np.fft.fftfreq`
  returns n/N; the shader's k-space uses integer modes n, so k = fftfreq·N·2π/L.
  A replica without the factor N is wrong by 64× at N=64 — invisible in RATIO
  measurements (scale-free) but it corrupts any multi-level combination that
  mixes grids of different N. Any two-level implementation must keep per-level
  normalization exact.

## 2. Findings (all measured; the menu)

| Lever | Ring anisotropy 2h/4h/8h | Phase spread (worst-dir @4h) |
|---|---|---|
| Baseline (k² symbol, O2 gradient) | 1.246 / 1.090 / 1.022 | 1.187 |
| O4 gradient (5-point central diff) | 1.200 / 1.045 / 1.007 | 1.120 |
| Dual grid, half-cell offset (O2) | 1.263 / 1.080 / 1.022 | 1.078 |
| **O4 + dual half-cell** | **1.133 / 1.034 / 1.005** | **1.041** |
| Dual, golden offset (φ⁻¹,φ⁻²,φ⁻³)·h | 1.51 (worse) | 1.250 (worse) |
| D19 k-space symbol (blob) | 1.411 (worse) | — |
| D7 symbol (blob) | 1.308 (worse) | — |
| Two-level naive multigrid / zoom patch | fails (see §3.3) | fails |

**Reading the table**

- **O4 + dual half-cell is the winner on both axes.** Placement bias excess drops
  **4.6×** (0.187 → 0.041) — that is the "bubbles in the wrong places" metric,
  and it clears the 3× adoption gate. Ring anisotropy at the bubble scale (2–4h)
  drops to 1.133 / 1.034.
- **The half-cell dual IS a BCC lattice.** Grid ∪ (grid + (½,½,½)h) is the
  body-centered cubic lattice: the two interleaved cubic sublattices are the two
  BCC parity classes. The dual average is therefore **BCC-lattice gravity**,
  realized with zero change to the Stockham FFT (two shifted cubic solves).
- **Golden offsets lose to half-cell for a 2-grid pair** (measured honest
  negative — the half-cell pair cancels the leading sawtooth; a single golden
  shift averages arbitrary phases). Golden offsets remain interesting only as a
  de-resonance research toggle, not as the default.
- **D19/D7 symbols worsen the blob near-field anisotropy** (confirms the
  earlier skill finding — no-op-to-worse for smooth sources). The 1/k² symbol
  stays.
- **O4 is nearly free**: it lives entirely in the gradient pass (O(N³) cells),
  does not touch the per-particle sampler cost.

## 3. The design — the cascade grid

### 3.1 Yin/Yang grid duality (BCC sampling)

The grid gains a dual partner: every per-step chain runs twice, once on the base
grid and once on the grid shifted by (h/2, h/2, h/2) per axis. Each particle
deposits mass into both sublattices; each particle samples the force field of
both; the forces are averaged. The pair of sublattices is the BCC lattice —
the densest, most isotropic 3D sampling at this density class — so the composite
grid has no single-cubic bias while the FFT, the φ-aspect extents, and the
19-point PDE stencil all survive untouched (a translation never enters the
k-space symbol).

Framework reading: the two fluids live on two lattices. EY deposits on the Yang
sublattice, EI on the Yin sublattice, the pair forming the dual lattice — the
grid itself becomes a Yin/Yang structure, and the phase-averaged force is the
force both fluids agree on. This is a design application of the duality
principle, not a new derivation (flagged as such).

**Cost:** 2× deposit + 2× spectral solve + 2× gradient pass + 2 gradient samples
per particle per step. The Poisson chain is not the bottleneck at N ≤ 64 (the
per-particle pass is), so the real cost is the second gradient sample.

### 3.2 Per-level 4th-order gradients

The gradient pass switches from 3-point to 5-point central differences
(4 extra `chord_s_at` evaluations per cell). Costless at the particle level;
measured wins in §2. The two-fluid PDE stays 19-point (it is already O(h²) in
physical ∇²); only the force gradient goes O4.

### 3.3 Multi-scale — the level pyramid (the answer: yes, with the honest caveats)

The naive two-level schemes were measured and FAIL — the spectral Green's
near-field is strongly grid-dependent (a 32³ delta Green is ~8× deep at 4 coarse
cells vs the 64³ Green at the same world point), and a half-box patch carries its
own periodic-image field (period 37.5 vs 75). A two-level force
`a = a_c + (a_f − a_cup)` therefore does not cancel cleanly: the coarse near-field
leaks through, and patch solves need coarse-supplied boundary conditions the
periodic Stockham FFT does not provide.

The cascade answer to multi-scale is three mechanisms, in order of cost:

1. **Multi-rung IC seeding (cheap — no solver changes).** Seed the initial
   density with power at φ-spaced wavenumbers k_n = k₀·φⁿ (a few rungs), so
   bubbles condense at several cascade rungs simultaneously — multi-scale
   structure without multi-grid. Combined with the φ-aspect box + dual + O4,
   each rung's placement is unbiased at its own scale.
2. **Coarse long-range level (medium).** A level at N/2 (N/4) supplies only the
   far-field part, applied with a smooth radial transition window (full coarse
   force for r ≳ 6–8 coarse cells, full fine force for r ≲ 4, blend between).
   The transition keeps the coarse Green's near-field (the measured failure
   zone) out of the bubble scale. Per-particle: one extra coarse gradient sample
   plus a window function.
3. **Zoom patch / true AMR (large, future).** A fine patch over the cluster with
   coarse-supplied boundary conditions. Requires non-periodic or windowed solves
   — a real project; not scheduled until 1–2 are in and measured.

### 3.4 φ-de-resonance kept

The φ-aspect box stays (box-scale de-resonance, GRID_LAYOUT.md). The dual offset
defaults to the half-cell (BCC); a golden-offset quasicrystal pair is a research
toggle only — measured worse for bias, honest framing: it buys de-resonance of
the grid pair, not bias reduction.

## 4. Honest limits

- The near-field r/h anisotropy never fully dies on a Cartesian lattice:
  residual ~1.13 at 2h / 1.03 at 4h with everything on. The structural fixes for
  the innermost scale are resolution (patch zoom) or a direct-sum near-field
  correction (PM/PP) — both deferred, both documented.
- The absolute force scale of the raw chain is ~1.6× the naive 1/(4πr²)
  convention at all radii/symbols (flat, not a shape error) — it is already
  absorbed by the sim's G_N calibration; nothing to change, but any new force
  term must go through the same calibration or it will be off by that constant.

## 5. Rollout plan

1. **O4 gradient pass** (smallest change; gradient pass only). Pin new cube
   anchors in verify_river_isotropy.gd.
2. **Dual (BCC) grid** — second deposit/solve/gradient chain + averaged nbody
   sampling; `dual_grid` export (default on after the battery). New grad
   buffer; md PC grows by the offset vector. Cube battery stays green at
   dual_grid = false (bit-identical path).
3. **Multi-rung IC seeding** — `multi_rung_seed` export: k_n = k₀·φⁿ density
   perturbations on the IC. Verify: no NaN, occupancy sane, bubble-size
   distribution visibly multi-scale.
4. **Coarse long-range level** (after 1–3 measured) — windowed two-level force.

Each commit keeps the repo runnable; the verify battery pins the new numbers
(the §2 table values become the regression anchors for dual = on).

## 6. Open items

- Confirm the per-particle cost of the second gradient sample at N_particles =
  2.5M (the nbody pass is the frame bottleneck; the dual may want a
  `dual_grid` default-off until measured on this rig).
- The transition window shape for the coarse level (measure, don't guess —
  same discipline as §2).
- Multi-rung seeding: pick k₀ and rung count from the resolved window
  (log_φ(N/2) ≈ 7.2 rungs at N = 64); seed 2–3 rungs below the cluster scale.
