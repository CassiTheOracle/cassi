# φ⁶-modulated gravity — is coherence-gated gravity the missing oblate mechanism? (wave 12b / U3)

**Pre-registered 2026-08-16.** This wave tests the LAST untested lever: the engine's full
coherence-modulated gravity `a = −G_N·(π/ρ)·∇(g·Φ)` with `g = 1 + (φ⁶−1)·q`, which wave-10 froze to
`g = 1` (a disclosed simplification). Hypothesis (U3): the φ⁶ chord factor — up to 18× gravity in
high-coherence cells — imprints the field's own transverse anisotropy (wave-10 true-frame
σ_x/σ_y ≈ 1.580) onto the collapsing particle cloud, possibly the missing axial-compression path.

## 0. The exact law (verbatim from `compute/cassi_nbody_gravity.glsl`, READ-ONLY)

- **Header (L7-17):**
  ```
  q     = ρ² / (ρ² + φ⁻² + ε²),    ρ = EY + EI,  ε = EY − φ·EI
  g     = 1 + (φ⁶−1)·q             (φ⁶−1 = pc.xi − 1, the chord coupling)
  ∇²Φ   = ρ_mass                   (Φ̂ = −ρ̂/k², k = 0 nulled, Φ < 0 at mass)
  a     = −G_N·(π/ρ)·∇(g·Φ)        — the FULL chord gradient in ONE pass
                                   (∇(gΦ) = g∇Φ + Φ(ξ−1)∇q; never hand-split)
  (π/ρ) = clamp((EY−EI)/(EY+EI), 0, 0.72)
  ```
- **`chord_g_from` (L499-518):** `rho_f = eyv + eiv`; `eps = eyv − pc.phi·eiv`;
  `q = rho_f²/(rho_f² + PHI_INV2 + eps²)` with `PHI_INV2 = φ⁻² = 0.3819660112501051`;
  `if rho_f < 1e-6: pi_over_rho = 0` else `pi_over_rho = clamp((eyv−eiv)/rho_f, 0.0, 0.72)`;
  `return 1.0 + (pc.xi − 1.0)·q`, `pc.xi = φ⁶ ≈ 17.9443`.
- **`chord_s_at` (L354-361):** `S(i,j,k) = (1 + (ξ−1)·q)·Φ[i,j,k]` — g and Φ at the SAME cell,
  whole product (no interpolation).
- **`grad_pass` (L431-466), 3-point (gradient order 2, the engine default):**
  `∇S = ((S[i+1]−S[i−1])/(2h_x), (S[j+1]−S[j−1])/(2h_y), (S[k+1]−S[k−1])/(2h_z))` with
  `h = extent/(N/2)`; periodic wraps. FORWARD central difference (+∇S). The river arm then does ONE
  trilinear sample of ∇S and multiplies `−G_N·π/ρ`.

## 1. Frozen setup (pins — NEVER changed after freezing; amendments dated)

- Reuse wave-10 machinery verbatim: `triaxial3d_particle_probe` (`seed_particles`, `deposit`,
  `trilinear_sample`, `field_sigma_physical`, `particle_sigma`, `physical_to_cell`,
  `wrap_physical`, `pi_over_rho_field`, `run_arm_a`, `run_arm_b`), `triaxial3d_feed_probe`
  (`make_poisson`, `N`, `SIM`, `EXTENT`, `G_N`, `DT`, `CLAMP_HI`), `triaxial3d` (`TwoFluid3D`,
  `seed_bubble3d`, `sigma3`).
- Pins: N=64, `SIM = h = (φ,1,φ²)`, `EXTENT = (φ,1,φ²)·32`, `N_p = 32768`, zero velocity,
  `σ₀ = 0.08·N = 5.12`, `rng_seed = 42`, per-particle mass 1/32768, `G_N = 1.0`, `DT = 0.02`,
  traces `t ∈ {200,600,1200,1800,2400}` (all inherited from wave-10).
- **Arm A** = wave-10 `run_arm_a` (free streaming; round guard [0.95, 1.05]).
- **Arm B** = wave-10 `run_arm_b` (g=1, π/ρ=1, `a = −G_N·∇Φ`). **Anchor:** MUST reproduce wave-10's
  reported trace to the wave-10 precision — σ_x/σ_y @2400 = 1.012, σ_x/σ_z @2400 = **1.001**,
  peak/p0 = 21.980. Tolerance ±0.005 (same machine, same numpy, identical code — expected bit-exact).
- **Arm C** = full coupling: wave-10 `run_arm_c` composition (particles + `TwoFluid3D` field +
  `0.001·ρ_mass` coupling, source_strength = 0), but the particle force replaces wave-10's g=1
  `∇Φ` with the law's **whole-product** `∇(g·Φ)`: build `S = g·Φ` on the grid (g from the UPDATED
  field, Φ from the current deposit's Poisson solve), take the FORWARD central difference ∇S
  (matching `grad_pass`), trilinear-sample ∇S at `p_new`, multiply `−G_N·π/ρ` with
  `π/ρ = clamp((EY−EI)/(EY+EI),0,0.72)` (ρ-guard <1e-6 → 0). Per-step order (engine order): deposit
  → Poisson → field PDE → 0.001·ρ_mass coupling → S = g·Φ → ∇S → KDK.
- **Statistics** (all arms, at each trace): particle σ_x/σ_y, σ_x/σ_z; arm C additionally field
  σ_x/σ_z (true frame), field σ_x/σ_y, sigma3 σ_x/σ_z, and particle peak/p0.

## 2. Frozen decision tree (primary statistic: σ_x/σ_z @ t=2400)

- **SUPPORTS** if arm-C particle σ_x/σ_z ≥ **1.05** (moves off the wave-10 1.00 baseline, above the
  round control's 1.008) **AND/OR** arm-C field σ_x/σ_z ≥ **1.218** (= 1.160 × 1.05, a ≥5% rise
  above the wave-10 1.160 baseline).
- **CONTRADICTS** if arm C reproduces the wave-10 isotropic collapse (particle σ_x/σ_z < 1.05, i.e.
  within noise of 1.00) **AND** the field is unchanged (field σ_x/σ_z < 1.218).
- **INCONCLUSIVE** on instability / NaN / amplitude floor (non-finite field or particle state; or a
  degenerate shape the round guard cannot bound).
- No threshold is weakened to make a gate pass.

## 3. Harness gates (`verify_triaxial3d_phigravity.py` → `ALL CHECKS PASSED`)

1. **G1 arm-B anchor:** `run_arm_b` @2400 reproduces σ_x/z = 1.001 ± 0.005 AND σ_x/y = 1.012 ±
   0.005 AND peak/p0 = 21.980 ± 0.005 (byte-reconciled to wave-10's report).
2. **G2 Poisson exactness:** single Fourier mode inversion rel err < 1e-9; mean(Φ) ≈ 0.
3. **G3 TSC partition:** single-particle deposit sums to 1.0 (center + fractional); full-cloud mass 1.0.
4. **G4 determinism:** arm C (φ⁶) 100-step double run bitwise identical.
5. **G5 no-NaN:** arm B and arm C finite on a short run.
6. **G6 (REPORTED):** arm-C particle peak/p0 @100 (collapse magnitude) and q/g range across the field.

### Amended-rule clause

The wave-10 numbers (1.008 / 1.001 / 21.980 / 1.160) are the calibration BASELINE, not gates except
the G1 anchor. Any post-freeze change to §1 is FORBIDDEN; a necessary change is disclosed as a dated
amendment appended here. Decision trees and thresholds are never weakened to make a gate pass.
