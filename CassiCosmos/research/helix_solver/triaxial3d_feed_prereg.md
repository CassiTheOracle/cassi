# Wave 9 — source-feed (Q1) and Poisson-gravity (Q2) on the sim's real (φ,1,φ²) operator — PRE-REGISTRATION

**Status:** Pre-registration — written BEFORE any probe run; governs the wave-9 arms.
**Date:** 2026-08-15 (continuation of the ultimate-Cassi-solver program).
**Workstream:** wave-9 — identify the mechanism behind the sim's oblate bubble record.
**Pre-registered outcomes:** whether the **sustained mass deposit** (Q1a), the **source field-gain**
(Q1b), or the field's own **Poisson-gravity self-coupling** (Q2) — each applied to the sim's real
fully-periodic (φ,1,φ²) 19-point anisotropic two-fluid operator — converts the wave-8 **prolate**
bubble (σ_x/σ_z = 0.329) toward the doctrine's **oblate** reference (σ_x/σ_z = 2.510; σ_x/σ_y =
φ = 1.618). Honest Reported Negatives (CONTRADICTS / DOES NOT EMERGE) are deliverables.
**Implementing probes (numpy, new-files-only, under `CassiCosmos/research/helix_solver/`):**
`triaxial3d_feed_probe.py`, `verify_triaxial3d_feed.py`, `triaxial3d_feed_report.md`
(this prereg). Run from `CassiCosmos/` (`cwd` = `CassiCosmos/`).

---

## 0. The question and the prior record

### 0.1 The wave-8 correction being investigated

Wave 8 (`triaxial3d_simop_corr_report.md`) established, decisively and correctly, that the sim's
**real two-fluid operator** — fully periodic `% N` on all axes, cell sizes `h_i = extent_i/(N/2)`
from the box extents `(φ, 1, φ²)` (`cassi_two_fluid.glsl` lines 53, 92–102) — turns a
**physically-round seed** into a **PROLATE, z-stretched** bubble: σ_x/σ_z = **0.329**, σ_x/σ_y =
**0.842** at 2400 steps. The doctrine's oblate reference (σ_x/σ_z = **2.510**, σ_x/σ_y = 1.422,
from `CassiTheory/visual-explainers/string_bubble_cascade.py`) therefore **cannot** come from the
pure two-fluid operator/dynamics alone. Wave 8's verdict: the compression must arise from the
**source/feed sector or the gravity sector** the operator-only probe excludes.

Wave 9 tests those sectors head to head on that same real operator.

### 0.2 The reference lines (NOT gates) and the framing

- **oblate reference:** σ_x/σ_z = **2.510** — a single-run **Python-PDE** output from
  `string_bubble_cascade.py` with a seed-inherited transverse ratio and a mismatched step label
  (code selects the step nearest 15000; docs say ~1100). It is **NOT an engine measurement** and
  the engine has **no bubble-shape readout**. Per the parallel provenance audit, 2.510 is an
  **unverified reference line**, not a gate.
- **transverse reference:** σ_x/σ_y = φ = **1.618** (doctrine) — also a REFERENCE, not a gate.
- **wave-8 prolate baseline:** σ_x/σ_z = **0.329**, σ_x/σ_y = **0.842** at 2400 steps on
  (φ,1,φ²). This is the start state the mechanism must convert.
- **Framing:** the Q1/Q2 verdicts stand on their own physics — *does the mechanism produce
  z-compression (σ_x/σ_z rising from ≈0.33 toward ≥1) on the sim operator, yes/no* — NOT on
  matching 2.510.

### 0.3 Grounding in the sim's engine and shader (quoted; verified by two independent worker reads)

**Operator** (`cassi_two_fluid.glsl` lines 86–146): 19-point anisotropic periodic stencil, weights
`b_ij = (1/3)·h₀²/(h_i²+h_j²)`, `a_i = h₀²/h_i² − 2(b_ij+b_ik)`, `h₀ = min(h)`; the shader's own
comment pins "(φ,1,φ²) → a=(0.127,0.731,−0.009), b=(0.092,0.035,0.042)", bit-identical to
`triaxial3d.lap_weights((φ,1,φ²))`; every axis wraps `% N`.

**Mass deposit — Q1a** (`cassi_mass_deposit.glsl` lines 4–18, 100–198): the sustained feed is the
per-step **TSC (triangular-shaped cloud) particle scatter** — a 27-cell separable quadratic
B-spline (`w_x(i)·w_y(j)·w_z(k)`), support 1.5h per axis, exact partition of unity (Σw = 1). It
runs **every step over live particle positions** and accumulates into the `MassDensity rho[]`
buffer. **This — not `source_strength` — is the engine's sustained mass feed.**

**Source field-injection — Q1b** (`cassi_two_fluid.glsl` lines 148–172, 212):
```glsl
// source_ey (center):  return source_strength·exp(−r2·4) + rho[cell]·0.001   (r2 cell-normalized)
// source_ei (OFFSET):  Gaussian at (0.7,0.8,0.6)·halfn, amp 0.707·source_strength, + rho[cell]·0.707·0.001
// ey_new = ey_old + vx·dt + source_ey·dt² ;  ei_new = ei_old + vy·dt + source_ei·dt²
```
So the field receives **two** per-step injections: (i) the **`0.001·ρ_mass` feedback** (EY; EI gets
`0.707·0.001·ρ_mass`) that couples the TSC-deposited mass density into the field — this is the
always-on feed that never turns off; and (ii) the **`source_strength·exp(−4r2)` field-gain**, with
`source_strength` default **0.0/off** (`cassi_sim.gd:63`, `cassi_physics_engine.gd:88`) and live
value **0.5** (`main.tscn`). Q1 splits these: **Q1a = the deposit feedback (i)**, **Q1b = the
field-gain (ii)** — separate frozen arms, separate verdicts (the provenance audit's explicit
request). Live sim = both; Q1b dominates (0.5 ≫ 0.001·ρ_mass at natural mass scales).
**Poisson-gravity — Q2** (`cassi_poisson.glsl` lines 9, 16–17, 147–158; `cassi_nbody_gravity.glsl`
lines 12–13, 344–362, 499–532): `∇²Φ = ρ_mass`, `Φ̂ = −ρ̂/k²`, **k = 0 nulled**, `k_i =
2π·kx_i/L_i`, `L_i = 2·extent_i` (per-axis torus periods). Force (attractive):
`a = −G_N·(π/ρ)·∇(g·Φ)` where `g = 1 + (φ⁶−1)·q`, `q = ρ²/(ρ²+φ⁻²+ε²)`, `ρ = EY+EI`,
`ε = EY−φEI`, `π/ρ = clamp((EY−EI)/(EY+EI), 0, 0.72)`, `φ⁻² = 0.381966`, `φ⁶ ≈ 17.944`. The
gradient is the **cell-centered central difference** of the whole product `S = g·Φ`
(`grad_pass`, `gradient_order=2`: `(S_{i+1}−S_{i−1})/(2h_i)`, `h_i = extent_i/(N/2)`).

## 1. Frozen setup (pins — NEVER changed after freezing; any amendment is dated)

- **Operator:** `triaxial3d.make_lap(h)` — the sim's exact 3D 19-point anisotropic periodic
  Laplacian, matrix-free via `np.roll`, with **h = (φ, 1, φ²)** (the SIM's real cell-size ratio).
  No other aspect.
- **Grid:** N = 64 per axis, fully periodic, uniform cells. `extent = (φ,1,φ²)·32` (half-box;
  `h_i = extent_i/(N/2)`, so `L_i = 2·extent_i = (φ,1,φ²)·64` for the Q2 Poisson torus periods).
- **Two-fluid dynamics** (`TwoFluid3D` half-kick staggered leapfrog):
  ∂²EY/∂t² = c²∇²EY − ω₀²(EY − φEI); ∂²EI/∂t² = c²∇²EI + ω₀²(EY − φEI); **c = 1.0, ω₀² = 20.0,
  dt = 0.02** (wave-8 pins).
- **Seed:** `seed_bubble3d(N, h, amp=0.3, sig_phys_frac=0.08)` — the **physically-round** 3D
  Gaussian (physical width equal on every axis; any emergent σ-anisotropy is purely the
  mechanism's, not the seed's). EY and EI co-located, EI = φ⁻¹·EY.
- **Run length / traces:** 2400 **steps**, traced at **step counts t = {200, 600, 1200, 1800,
  2400}** ("t" = step index; peak0 = max|EY+EI| at step 0).
- **Measures:** `sigma3(|EY+EI|, h)` → σ_x, σ_y, σ_z (physically scaled ×h_i); report σ_x/σ_y,
  σ_x/σ_z and `peak/peak0 = max|EY+EI|(t)/peak0`.
- **Determinism:** numpy-only; NO RNG in the physics; matrix-free (never a dense N³×N³ operator).

### 1.1 Q1a — sustained TSC mass-deposit feedback (frozen)

Faithful to `cassi_mass_deposit.glsl` + the `0.001·ρ_mass` feedback in `source_ey`/`source_ei`:

- **Deposit:** a fixed, physically-round Gaussian **mass cloud at the box center**, re-seeded
  every step (same profile), total mass M = 1.0, σ = 0.08·N (matching the field seed width),
  scattered through the **exact TSC B-spline kernel**. For a cell-centered cloud (f = 0) the TSC
  1D weights are `[0.125, 0.75, 0.125]` (from `w(−1)=½(½−f)², w(0)=¾−f², w(+1)=½(½+f)²`), so the
  deposit `ρ_mass` is the **3D separable convolution** of the Gaussian mass profile with
  `[0.125, 0.75, 0.125]⊗³` — the exact 27-cell quadratic-B-spline scatter, partition of unity.
- **Field injection (every step, after the leapfrog):**
  `EY ← EY + 0.001·ρ_mass·dt²`; `EI ← EI + 0.000707·ρ_mass·dt²` (the shader's `0.001·ρ` on EY
  and `0.707·0.001·ρ` on EI — the asymmetric Yin–Yang mass feedback).
- **Control:** identical run with the injection = 0 (pure wave-8 case; MUST reproduce σ_x/σ_z ≈
  0.329 — the sanity anchor).

### 1.2 Q1b — source_strength field-gain (frozen)

Faithful to `source_ey`/`source_ei` at the live-sim `source_strength = 0.5`:

- **EY gain (centered, every step):** `EY ← EY + 0.5·exp(−4·r2)·dt²`, `r2 = dx²+dy²+dz²`,
  `dx = (i − halfn)/halfn` (cell-normalized, as the shader).
- **EI gain (OFFSET, every step):** `EI ← EI + 0.5·0.707·exp(−4·r2_off)·dt²`, with the offset
  Gaussian centered at `(0.7, 0.8, 0.6)·halfn` (the shader's Yin–Yang separation — the only
  non-centered element in the sim's source).
- **Control:** identical run with the gain = 0 (pure wave-8 case).

### 1.3 Q2 — field Poisson-gravity self-coupling, g = 1 simplification (frozen)

The engine's exact solve + coupling form, applied to the field's own density, with the **stated,
frozen** simplification `g = 1` (plain attractive `−G_N·(π/ρ)·∇Φ`; the full `g = 1+(φ⁶−1)q`
chord factor is excluded as the documented simplification, per the provenance audit's option):

- **Poisson source:** `ρ_source = |EY+EI|` (positive-definite field-mass proxy).
- **Solve (spectral, exact):** `Φ̂(k≠0) = −ρ̂_source(k)/k²`, **k = 0 nulled**; `k² = Σ_i (2π·kx_i/L_i)²`
  with `L_i = 2·extent_i = (φ,1,φ²)·64` and `kx_i` the cyclic fftfreq labels (n ≤ N/2 → +n,
  n > N/2 → n−N — the shader's exact convention). `Φ = ifftn(Φ̂).real`.
- **Gradient (cell-centered central difference, 3-point, as `grad_pass`):** `∇Φ_x =
  (Φ[i+1]−Φ[i−1])/(2·h_x)`, `h = (φ,1,φ²)` (extent_i/(N/2)).
- **Coupling prefactor:** `π/ρ = clamp((EY−EI)/(EY+EI), 0, 0.72)` with a `|EY+EI| < 1e-6 → 0`
  guard (the shader's `rho_guard`).
- **Scalar-coupling (frozen — the two-fluid is SCALAR):** EY, EI are scalar fields with scalar
  velocities (`cassi_two_fluid.glsl` `vel = (∂EY/∂t, ∂EI/∂t, 0, ε²)` — no spatial vector). The
  engine's vector body force `a = −G_N·(π/ρ)·∇Φ` acts on *particles* there; for the field-only
  self-gravity probe the vector force couples to the scalar field through the momentum–continuity
  combination, giving the scalar gravity source
  `S_grav = +G_N·∇·( m·∇Φ )`,  `m = ρ·clamp((EY−EI)/ρ, 0, 0.72)`  (the momentum-density prefactor;
  `m = ρ·(π/ρ) = EY−EI = Π` when unclamped), `ρ = EY+EI`.
  `S_grav` is added as **½·S_grav to EY's acceleration and ½·S_grav to EI's acceleration** each
  step, so the total charge ρ = EY+EI receives `S_grav`. **G_N = 1.0** (the engine's
  IC-consistent scale). At a mass peak this reduces to `≈ +G_N·π_eff·ρ² > 0` — attractive,
  Jeans-like growth (the sign is checked in the gate). Recomputed from the current field every
  step. `∇·` uses the same 3-point periodic central difference as `∇`.
- **Control:** identical run with `S_grav = 0` (pure wave-8 case).

### 1.4 Implementation structure (new-files-only)

All new code lives in `triaxial3d_feed_probe.py` and `verify_triaxial3d_feed.py`, importing the
existing `triaxial3d`, `phi_grid.PHI`, and `edge_proxy`. **`triaxial3d.py`, `verify_triaxial3d.py`
and every other existing file are NOT modified.** The Poisson symbol/k² grid, TSC deposit, field
gain, and gravity kick are additive functions in the probe module, built deterministically from
`triaxial3d.lap_weights(h)`.

## 2. The questions and decision trees

### Q1a — does the sustained TSC mass-deposit feedback convert the prolate bubble toward oblate?

**Statistic:** σ_x/σ_z(t) and σ_x/σ_y(t) on the Q1a arm vs the no-feed control, at the frozen
traces; primary statistic σ_x/σ_z @ t=2400.

| Verdict | Condition (σ_x/σ_z @ t=2400) |
|---|---|
| **SUPPORTS** | Q1a σ_x/σ_z rises substantially from the ≈0.33 control toward ≥ 1, ideally into **[1.8, 3.2]**; AND the control stays ≈ prolate (σ_x/σ_z ≤ 0.6) |
| **CONTRADICTS / DOES NOT EMERGE** | Q1a σ_x/σ_z shows no material rise (≤ 0.6) or moves **more** prolate; OR the control does NOT reproduce ≈0.33 (harness anomaly) |
| **INCONCLUSIVE** | instability (non-finite field) OR amplitude-decay floor (Q1a peak/peak0 < 0.10 at t=2400) |

σ_x/σ_y REPORTED for both arms (reference φ = 1.618, not a gate).

### Q1b — does the source_strength field-gain convert the prolate bubble toward oblate?

**Statistic:** σ_x/σ_z(t) and σ_x/σ_y(t) on the Q1b arm vs the no-gain control; primary statistic
σ_x/σ_z @ t=2400. Same verdict table as Q1a (mutatis mutandis: Q1b arm).

### Q2 — does the field's own Poisson-gravity self-coupling (g=1) convert the prolate bubble toward oblate?

**Statistic:** σ_x/σ_z(t) and σ_x/σ_y(t) on the Q2 arm vs the no-gravity control; primary
statistic σ_x/σ_z @ t=2400.

| Verdict | Condition (σ_x/σ_z @ t=2400) |
|---|---|
| **SUPPORTS** | Q2 σ_x/σ_z rises substantially from the ≈0.33 control toward ≥ 1, ideally into **[1.8, 3.2]**; AND the control stays ≈ prolate (σ_x/σ_z ≤ 0.6) |
| **CONTRADICTS / DOES NOT EMERGE** | Q2 σ_x/σ_z shows no material rise (≤ 0.6) or moves more prolate; OR control does NOT reproduce ≈0.33 |
| **INCONCLUSIVE** | instability (non-finite) OR amplitude-decay floor (Q2 peak/peak0 < 0.10) |

σ_x/σ_y REPORTED for both arms (reference φ = 1.618, not a gate).

### Amended-rule clause

The record 2.510 and φ = 1.618 are REFERENCE lines, NOT gates. Any post-freeze change to any pin
in §1 is FORBIDDEN; a necessary change is disclosed as a dated amendment appended to this document
and the affected arm re-frozen before re-run. Neither decision trees nor numeric pins are weakened
to make a gate pass.

**Amendment 2026-08-16 (decision-tree precedence, disclosed before the re-run):** the amplitude
floor ("peak/peak0 < 0.10 → INCONCLUSIVE") is intended to guard against an *unmeasurable* σ-shape.
The pure control arm decays to peak/peak0 = 0.091 at t=2400 (the free dispersive wave's natural
end-state — the wave-8 anchor 0.329 is itself this 9.1% state), so the 10% threshold sits *above*
the baseline's own natural decay. A deterministic (no-RNG) σ_x/σ_z ≤ 0.6 is therefore a definitive
measured negative, not an inconclusive one. The floor is accordingly **reported as a caveat flag
appended to the verdict** (not the primary verdict) when the arm's peak/peak0 < 0.10; the SUPPORTS
(≥ 1.0) and CONTRADICTS/DOES NOT EMERGE (≤ 0.6) thresholds are unchanged. No numeric pin was
weakened; this only clarifies the precedence of the three INCONCLUSIVE triggers against the
deterministic measured negative.

## 3. Harness gates (verify_triaxial3d_feed.py, unconditional, must ALL PASS → prints `ALL CHECKS PASSED`)

1. **G-free-conservation:** the free (ω₀²=0) two-fluid energy drift < 5e-3 over 2400 steps on the
   (φ,1,φ²) uniform grid (uniform-grid conservation; no feed/gravity in this arm).
2. **G-determinism:** the Q1a, Q1b and Q2 arms are each bitwise identical across two identical
   100-step runs (exercises the TSC deposit, field-gain and FFT-Poisson gravity paths).
3. **G-no-NaN:** all arms (control, Q1a, Q1b, Q2) finite at all five trace times (checked on a
   short deterministic run for the gates, full traces in the probe).
4. **G-poisson:** (a) the exact-Fourier Poisson solve inverts a single Fourier mode to float
   precision (`Φ = −ρ/k²`, k=0 nulled, Φ mean-zero — checks the k² grid, axis order, sign); (b) the
   gradient/divergence wiring is exact: `div(grad(u))` equals the discrete symbol
   `−Σᵢ sin²(2πnᵢ/N)/hᵢ²·u` on a single mode to float precision; (c) the gravity source is
   attractive (positive `S_grav` at a positive mass peak). No RNG.
5. **G-seed-round:** the physically-round seed on (φ,1,φ²) gives σ_x/σ_y, σ_x/σ_z ∈ [0.95, 1.05]
   at start, and non-wrapping (z-boundary mass ≈ 0).
6. **Sanity:** the pure control reproduces the wave-8 prolate anchor σ_x/σ_z ∈ [0.15, 0.60] at
   2400 steps; no NaN; C_dyn finite.

## 4. Stopping rule

Fixed: one physically-round seed, N=64, 2400 steps, four arms (control / Q1a / Q1b / Q2) on the
single (φ,1,φ²) operator, one analysis, deterministic. A CONTRADICTS / DOES NOT EMERGE is final
for this wave. Only a new dated pre-registration re-opens.

## 5. What does NOT count

- Post-hoc N, steps, dt, aspect, seed, source_strength, G_N, threshold, ρ-choice, g-factor, or
  weights changes.
- Reading σ-shape as the edge-steepness 1.70 (a different quantity).
- Claiming the numpy probe as the full Godot engine (no shader/engine/scene change here).
- Modifying `triaxial3d.py`, `verify_triaxial3d.py`, or any existing file.

## 6. Honest tiers

- **T1 measured** — σ ratios, peak/peak0, energy drift, determinism, Poisson-solve consistency on
  all arms.
- **T2 inferred** — "the deposit feedback / field-gain / field self-gravity does/does not convert
  the prolate bubble".
- **T3 out of scope** — the full Godot engine (particle nbody, BH accretion, dual-grid, gradient
  order 4, RealSim dissipation, meshless arm, calibrated G_N); any engine/scene/registry edit.

## 7. Number provenance

- PDE, 19-point stencil, weights, cell sizes, source field-injection form:
  `CassiCosmos/compute/cassi_two_fluid.glsl` (lines 53, 86–146, 148–172, 212).
- TSC mass deposit: `CassiCosmos/compute/cassi_mass_deposit.glsl` (lines 4–18, 100–198).
- Poisson solve, k-space convention: `CassiCosmos/compute/cassi_poisson.glsl` (header, 147–158).
- River field force / g / q / π/ρ / G_N / gradient: `CassiCosmos/compute/cassi_nbody_gravity.glsl`
  (lines 12–13, 344–362, 499–532).
- Box aspect, source_strength defaults/live, gravity_mode, cluster_radius, box_scale:
  `CassiCosmos/scripts/cassi_physics_engine.gd` (`box_aspect`, `source_strength=0.0`),
  `CassiCosmos/scripts/cassi_sim.gd:63`, `CassiCosmos/scenes/main.tscn` (`source_strength=0.5`,
  `cluster_radius=80.0`, `box_scale=3.0`, `gravity_mode=4`, `black_holes_enabled=true`).
- Wave-8 prolate baseline and verdict: `triaxial3d_simop_corr_report.md`.
- Doctrine oblate reference: `CassiTheory/visual-explainers/string_bubble_cascade.py` (2.510 /
  1.422 — unverified reference, per §0.2).
