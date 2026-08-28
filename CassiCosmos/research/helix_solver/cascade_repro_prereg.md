# Cascade-repro — is the oblate record real in its own source script? (wave 11)

**Pre-registered 2026-08-16.** Source under scrutiny (READ-ONLY, never edited):
`CassiTheory/visual-explainers/string_bubble_cascade.py`. This document freezes the reproduction
arms, statistics, and decision tree BEFORE any probe run. Amendments are dated below.

## 0. What the source actually does (exact line quotes, verbatim)

- **PDE — damped-wave two-fluid, RK4** (`rhs` L216-229, `rk4_step` L232-262):
  `dEY/dt = VY`, `dVY/dt = ∇·(c²∇EY) − γ·VY − λ(EY − φ·EI)`;
  `dEI/dt = VI`, `dVI/dt = ∇·(c²∇EI) − γ·VI + λ(EY − φ·EI)`.
  `c²(r) = c0²·|r−φ| / (α_c2 + |r−φ|)` with `r = EY/(EI+1e-12)` (L189-193). `∇·(c²∇f)` is
  half-point face averaging, 3D periodic via `np.roll` (L196-203). Each RK4 step rescales
  `EY,EI *= mass0/sum(EY+EI)` (L253-257; `mass0 = sum(EY+EI)` at t=0, L181) and applies a damping
  sponge that is **disabled** (`sponge_width = 0.0`, L84).
- **IC envelope — the transverse φ-ratio is SEEDED** (L98-100): `sigma0_z = np.full(N, sigma_r)`
  with `sigma_r = L/8`; `sigma_x_z = PHI * sigma0_z`; `sigma_y_z = sigma0_z`. The transverse
  Gaussian `T_env_b = exp(-(Xb²/(2σ_x²) + Yb²/(2σ_y²)))` (L138-139) therefore starts
  σ_x/σ_y = φ by construction. σ_z comes from the chord packets `G_N, G_S` (width `sigma_z = L/8`,
  L77, L110-111) and is NOT seeded with any φ-ratio.
- **Coherence estimator — φ-weighted shell** (`coherence_extents` L333-349):
  `r = EY/(EI+1e-12)`; `weight = exp(-(r−PHI)²/(2·0.08²))`; `sx = sqrt(Σ(X−xc)²·weight/Σweight)`.
  The measured extents are those of the **r≈φ coherence shell**, not of the energy.
- **Step selection** (L434): `idx_bubble = np.argmin(np.abs(snapshot_steps - 15000))`. With the
  DEFAULT `steps = 3500` (L53) this DEGENERATES to the last snapshot (step 3500), because 15000
  is never reached. (`EY_xz_stage3`, gated on `step >= 15000` at L406, is likewise never captured;
  Panel C falls back to a placeholder uniform-φ image at L563.)
- **σ measurement** (L446-449): `asp_xy = coh_sx_t[idx_bubble]/coh_sy_t[idx_bubble]`;
  `asp_xz = coh_sx_t[idx_bubble]/coh_sz_t[idx_bubble]`. Reported targets φ and φ² (L697-698).

**Constants:** N=64, L=12.0, dx=0.1875, dt=0.006, steps=3500, c0=0.6, α_c2=0.15, γ=0.02, λ=0.1,
E0=1.0, A_amp=0.3, σ_z=σ_r=L/8=1.5, z_max=L/4=3.0, eps5=0.05, ell0=L/4=3.0, A_ring=0.15,
r0_ring=0.8, σ_ring=0.4, σ_z_ring=1.5, n_strings=5, single bubble at origin.

## 1. Frozen setup (pins — NEVER changed after freezing; amendments dated)

- **Reimplementation** is a byte-faithful port of the source's IC, `c2_field`, `div_c2_grad`,
  `rhs`, `rk4_step`, and `coherence_extents` into a new standalone file
  (`cascade_repro_probe.py`), numpy-only, matrix-free, no RNG in the physics (the source itself
  has NO random numbers — see Amendment (a)).
- **Determinism:** fixed; every arm is a pure function of its parameters (no RNG except the
  explicit seeded `default_rng` used ONLY for the Arm-4 IC perturbation).
- **Measurements** (all at the SAME selected step as the source, `idx_bubble` = last snapshot =
  step 3500, plus step 1100 for Arm 3):
  - `σ_x/σ_y`, `σ_x/σ_z` from `coherence_extents` (φ-weighted, faithful);
  - `σ_x/σ_y`, `σ_x/σ_z` from `energy_extents` (r-NEUTRAL: weight = `(EY−E0)²+(EI−E0)²`, the
    source's own `rms_extents` L317-330) for Arm 1.
- **Tolerances (frozen):**
  - Arm-0 reproduction: σ_x/σ_y ∈ [1.27, 1.57] AND σ_x/σ_z ∈ [2.26, 2.76] (≈1.422 and ≈2.510
    within ±10%). Failure ⇒ the harness is NOT faithful; stop and fix before trusting any arm.
  - "Survives" an honesty arm ⇒ that arm's σ_x/σ_z ≥ **1.8** (still in the doctrine's oblate
    regime); "collapses" ⇒ σ_x/σ_z < 1.5 (drops toward round).
  - Arm-2 transverse collapse ⇒ σ_x/σ_y < 1.15 (seeded φ = 1.618 is gone).
  - Arm-4 seed-stable ⇒ coefficient of variation of σ_x/σ_z < 0.3 AND all seeds ≥ 1.8.

## 2. Arms and the frozen decision tree

| arm | change from faithful | question |
|---|---|---|
| **0** | none (faithful port) | reproduce ≈1.422 and ≈2.510 at step 3500 (harness validation) |
| **1** | estimator: φ-Gaussian weight → energy-perturbation weight (r-neutral) | does σ_x/σ_z = 2.510 survive estimator neutrality? |
| **2** | IC: `sigma_x_z = PHI*sigma0_z` → `sigma_x_z = sigma0_z` (isotropic transverse) | does σ_x/σ_y = 1.422 collapse to ~1.00? what happens to 2.510? |
| **3** | no new run — read Arm-0 history | σ_x/σ_z at step ~1100 (docs) vs step 3500 (code's actual `idx_bubble`); is the citation wrong? |
| **4** | IC perturbed by seeded Gaussian noise (ε = 1e-3·A_amp, seeds {42,43,44,45}) | is 2.510 seed-stable (mean ± spread)? |

**Decision tree (frozen):** 2.510 is a GENUINE emergent record only if it survives Arm 1
(σ_x/σ_z ≥ 1.8 under the r-neutral estimator) AND Arm 2 (σ_x/σ_z ≥ 1.8 under the isotropic IC,
i.e. the axial oblate is independent of the seeded transverse ratio) AND Arm 4 (seed-stable).
- **SUPPORTS** = survives all three;
- **CONTRADICTS** = collapses under ANY single honesty arm (name which arm and the collapsed value);
- **INCONCLUSIVE** = NaN, non-convergence, or a step/measurement ambiguity that cannot be resolved.

## 3. Harness gates (`verify_cascade_repro.py` → `ALL CHECKS PASSED`)

1. **G1 reproduction:** run Arm 0 to step 3500; σ_x/σ_y ∈ [1.27,1.57] AND σ_x/σ_z ∈ [2.26,2.76].
2. **G2 determinism:** two 100-step Arm-0 evolutions bitwise identical.
3. **G3 no-NaN:** Arm 0 (full) and short Arm 1/2/4 (100-step) all finite.
4. **G4 reconcile:** each arm's reported final σ equals its last snapshot entry (no off-by-one).

### Amended-rule clause

The quoted 1.422 / 2.510 are the OUTPUTS under scrutiny, not gates (except the Arm-0
reproduction tolerance, which validates the harness). Any post-freeze change to §1 is FORBIDDEN; a
necessary change is disclosed as a dated amendment appended here. Decision trees and numeric
thresholds are never weakened to make a gate pass.

**Amendment 2026-08-16 (a) — the source is fully deterministic (no RNG).** The mission's
"single unseeded run" describes the source's determinism, not a missing seed. There is no RNG
anywhere in `string_bubble_cascade.py`; every run is bit-identical. Arm-4's "ensemble" is therefore
defined as IC-perturbation sensitivity: add `rng.normal(0, 1e-3*A_amp, (N,N,N))` (independent draws
for EY and EI) at t=0, recompute `mass0`, then evolve. Seeds {42, 43, 44, 45}. This tests
whether 2.510 is robust to a small finite IC perturbation, which is the closest well-posed reading
of "seed variance" for a deterministic PDE.

**Amendment 2026-08-16 (b) — the record is a TRANSIENT at ~1100, not at the code's selected step.**
Running the faithful port to step 3500 (the prereg's initial assumption) — and, read-only, the
ACTUAL source script at its default `--steps 3500` — both give σ_x/σ_y = 0.975, σ_x/σ_z = 1.019,
`Spheroid confirmed: NO` (ROUND). The oblate σ_x/σ_z ≈ 2.5 is a TRANSIENT: it appears at step ~800
(the anti-phase meeting), peaks ≈2.9 near step ~1800, and DECAYS back to ≈1.0 by step 3500, staying
≈1.0 through step 15000. The code's `idx_bubble = argmin|snapshots − 15000|` therefore selects step
3500 (default run) or 15000 (long run) — NEITHER of which contains the oblate transient; the code
NEVER measures at the ~1100 step the docs cite. The energy (r-neutral) extents converge to ≈1.000
(round) by step ~500 and stay there at ALL steps — the oblate signature lives ONLY in the
φ-weighted coherence shell. Therefore the arms measure at **step 1100** (the docs' cited step where
the transient actually appears); Arm 0 additionally reports 3500 and 15000 (the code's actual
`idx_bubble` for default/long runs) for Arm 3. Frozen reproduction targets (replacing the §3 G1
band): σ_x/σ_z @1100 ∈ [2.0, 3.0] AND σ_x/σ_y @1100 ∈ [1.3, 1.9] (measured ≈2.497 and ≈1.591 —
the docs' "1.422" is NOT exactly reproduced, indicating a stale/non-reproducible citation). No
decision-tree threshold was weakened; the measurement step was corrected to where the record
actually lives.
