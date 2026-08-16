# Wave 10 — particle-nbody gravity on the sim's periodic (φ,1,φ²) box — PRE-REGISTRATION

**Status:** Pre-registration — written BEFORE any probe run; governs the wave-10 arms.
**Date:** 2026-08-16 (continuation of the ultimate-Cassi-solver program).
**Workstream:** wave-10 — the last untested sector: the engine's **particle-nbody gravity**.
**Pre-registered outcomes:** whether the particle-gravity sector imprints **oblate (z-compressed)**
structure on a physically-round collisionless particle cloud in the sim's periodic (φ,1,φ²) box,
and whether the particle-driven mass distribution can **deform the two-fluid coherence bubble's
shape** (the "doctrine quantity"). Honest Reported Negatives (CONTRADICTS) are deliverables — an
ALL-CONTRADICTS result is a fine outcome.
**Implementing probes (numpy, new-files-only, under `CassiCosmos/research/helix_solver/`):**
`triaxial3d_particle_probe.py`, `verify_triaxial3d_particle.py`, `triaxial3d_particle_report.md`
(this prereg). Run from `CassiCosmos/`.

---

## 0. The question and the prior record

### 0.1 Why this sector is the last untested one

Waves 8 (operator correction) and 9 (feed/gravity) ruled out **field-only** mechanisms: on the sim's
real fully-periodic (φ,1,φ²) 19-point anisotropic two-fluid operator with a physically-round seed,
σ_x/σ_z = 0.329 @2400 (prolate); sustained TSC mass-deposit feedback, the source field-gain, and the
field's own Poisson self-gravity (g=1) all give **DOES NOT EMERGE** (`triaxial3d_feed_report.md`).
The provenance audit (`oblate_provenance_audit.md`, committed 27ad20f) established the doctrine's
"oblate record" (σ_x/σ_y = 1.422, σ_x/σ_z = 2.510) is **NOT an engine measurement** — single-run
Python-PDE outputs (`string_bubble_cascade.py`), with σ_x/σ_y heavily seeded-in and σ_x/σ_z an
unseeded single-run result at a mismatched step label. Wave 10 tests the one sector untouched so
far: the **particle-nbody gravity** where the force acts on *particles* (not the field), particles
move under KDK, and mass re-deposits via TSC scatter into the gravity density channel.

### 0.2 Reference lines (NOT gates) and framing

- **oblate reference:** σ_x/σ_z = **2.510** — a *field-coherence* quantity from a single-run
  Python PDE, **not** an engine measurement (audit §1, §4). REFERENCE, not a gate.
- **transverse reference:** σ_x/σ_y = φ = **1.618** — also a REFERENCE, not a gate (mostly seeded-in).
- **wave-9 field baseline:** the two-fluid bubble's true-physical σ_x/σ_z ≈ **1.16** (this is
  σ_x/σ_z = 0.329 in the wave-9 `sigma3` transposed frame — see §1.5 for the axis-frame
  reconciliation; both are the SAME field).
- **Framing:** the wave-10 verdicts stand on their own physics — *does the particle-gravity sector
  produce z-compression (oblate) on the periodic (φ,1,φ²) box, yes/no* — NOT on matching 2.510.

### 0.3 Engine facts quoted (from `oblate_provenance_audit.md` §3 + shaders)

- **Box:** `box_aspect = Vector3(1.618, 1.0, 2.618)` = **(φ, 1, φ²)**; x = Yang (extended),
  y = Yin, z = String/flow (`cassi_physics_engine.gd:105`, `cassi_sim.gd:257-261`). `_extents() =
  box_aspect·(cluster_radius·1.5)·box_scale` is "the single source of truth for the box geometry".
- **Mass deposit:** per-step **TSC particle scatter** — a 27-cell separable quadratic B-spline,
  exact partition of unity, support 1.5h/axis, accumulating into `MassDensity rho[]`
  (`cassi_mass_deposit.glsl:5-11,100-108`). "runs every step over the live particle buffer".
  `source_strength` default **0/off** is a scalar field-injection gain, not a re-seed
  (`cassi_sim.gd:63`).
- **Poisson:** spectral Stockham FFT, `∇²Φ = ρ_mass`, `Φ̂ = −ρ̂/k²`, **k = 0 nulled**, per-axis
  torus periods `L_i = 2·extent_i` (`cassi_poisson.glsl:9,16-17,147-158`).
- **Φ → particle coupling:** cell-centered `∇(g·Φ)` (3-point central differences), force
  `a = −G_N·(π/ρ)·∇(g·Φ)`, whole product never hand-split; `g = 1 + (φ⁶−1)·q`,
  `q = ρ²/(ρ²+φ⁻²+ε²)`, `ε = EY−φEI`, `π/ρ = clamp((EY−EI)/(EY+EI), 0, 0.72)`, G_N = bh[1].w
  (`cassi_nbody_gravity.glsl:12-13,344-362,499-532`).
- **Engine never measures a bubble shape** (audit §3c) — the 2.510 is not an engine observable.

## 1. Frozen setup (pins — NEVER changed after freezing; any amendment is dated)

- **Box/grid:** fully periodic, N = 64 per axis, extents (φ,1,φ²). Cell sizes
  `h = (φ, 1, φ²)` (ratio; `h_i = extent_i/(N/2)`, `extent = (φ,1,φ²)·32`); torus periods
  `L_i = 2·extent_i = (φ,1,φ²)·64`. Same conventions as waves 8/9.
- **Seed — physically-round collisionless particle cloud:**
  - N_p = **32768** particles, **zero initial velocity** (cold — gravity is the only evolving
    force; the "free-streaming" guard arm stays round).
  - Positions sampled from an **isotropic 3D Gaussian in physical coordinates**, σ₀ = **0.08·N =
    5.12** physical units (matches `seed_bubble3d`'s physical radius), via
    `np.random.default_rng(42)` — **FIXED seed** (used once for initial positions; NO RNG in the
    integrator/deposit/Poisson, so the physics is deterministic given the seed).
  - Map to continuous cell coords `c_a = p_a/h[a] + N/2`, periodic wrap into [0, N).
  - Per-particle mass = 1/N_p (total mass M = **1.0**).
- **Integrator:** the engine's cached-acc **KDK** (velocity-Verlet): one warm-up acceleration at
  p₀, then `v½ = v + a_prev·dt/2; p' = p + v½·dt; a' = F(p'); v' = v½ + a'·dt/2`. dt = **0.02**.
- **Deposit:** exact TSC 27-cell separable quadratic B-spline scatter of each particle's mass
  (fractional cell weights `w_x·w_y·w_z`, partition of unity, periodic wrap) →
  `ρ_mass`. Re-computed **every step** from live particle positions.
- **Poisson:** engine-exact `Φ̂ = −ρ̂/k²`, k=0 nulled, `k_i = 2π·kx_i/L_i`, `L_i = 2·extent_i`
  (np.fft, deterministic).
- **Gradient:** 3-point cell-centered central difference, `h = (φ,1,φ²)`.
- **Measure:** particle-cloud σ in **engine-frame physical coordinates**: axis a physical =
  `(c_a−N/2)·h[a]`; `σ_x = std(p_x)`, `σ_y = std(p_y)`, `σ_z = std(p_z)` where axis0 = x (φ-extent),
  axis1 = y, axis2 = z (φ²-extent). "Round" = σ_x/σ_z = 1.000; **oblate (z-compressed)** = σ_x/σ_z
  > 1. The field bubble (arm C) is measured with BOTH a true-physical σ helper and `t3.sigma3`
  (cross-reference).
- **Trace times:** t ∈ {200, 600, 1200, 1800, 2400} **steps** (2400 total). peak0 = max density
  at step 0 (for the amplitude-floor rule).
- **Gravity constant:** G_N = **1.0** (the engine's IC-consistent scale), **g = 1** frozen
  simplification of the river force (the full `g = 1+(φ⁶−1)q` chord factor is excluded as the
  documented simplification, per the provenance-audit option — see §1.4/1.5).

### 1.4 Arms and the frozen π/ρ conventions

- **A — free-streaming control (no gravity):** particles at rest, no force. **Gate:** stays round
  (σ ratios ≈ 1.000).
- **B — engine gravity, g=1, π/ρ≡1:** particles under `a = −G_N·∇Φ` from Poisson(ρ_TSC). The
  shader's `π/ρ = (EY−EI)/(EY+EI)` is a **field** factor undefined without a two-fluid field, so
  arm B freezes **π/ρ ≡ 1** (the neutral/cold limit). This isolates pure particle-nbody
  self-gravity `a = −G_N·∇Φ` on the periodic (φ,1,φ²) box. **Primary answer to "does the particle
  sector compress z?"**
- **C — full composition:** particles under `a = −G_N·(π/ρ)·∇Φ` with
  `π/ρ = clamp((EY−EI)/(EY+EI), 0, 0.72)` (+ ρ<1e-6 → 0 guard) **sampled from the evolving
  two-fluid field** at each particle position (trilinear). The field evolves by the **wave-8
  machinery** (`make_lap((φ,1,φ²))`, ω₀²=20, c=1) from `seed_bubble3d` (amplitude 0.3, physically
  round), with `source_strength = 0` (off — isolates particle-gravity, not the wave-9 field-gain)
  and the shader's always-on particle coupling `EY += 0.001·ρ_mass·dt²`,
  `EI += 0.000707·ρ_mass·dt²`. Measure **both** the particle-cloud σ and the field-coherence σ.

### 1.5 Axis-frame reconciliation (the wave-9 "prolate" vs wave-10 "round")

The wave-8/9 field probes measure σ with `triaxial3d.sigma3`, which labels **axis2 as "x" (×h[0])**
and **axis0 as "z" (×h[2])** — transposed relative to the engine's axis0 = x = φ. On a
physically-round-in-engine-frame field this transposed measure returns σ_x/σ_z = 1/φ² ≈ 0.382 at
start, and σ_x/σ_z = 0.329 @2400 (the wave-9 "prolate" anchor). In **true engine-frame physical
coordinates** the SAME field is σ_x/σ_z ≈ **1.16** @2400 (slightly x-extended; see the report's
derivation). Wave 10 measures particles and the arm-C field in the **true physical frame**
("round" = 1.000, "oblate" = σ_x/σ_z > 1) to answer the physical question unambiguously; the
arm-C field's `sigma3` value is reported as a cross-reference. This is a measurement-frame
choice, not a physics result for the field (wave-9's DOES-NOT-EMERGE verdicts are unaffected).

## 2. Questions and decision trees (frozen)

### Q1 (arms A vs B) — does particle-nbody self-gravity (g=1, π/ρ=1) produce oblate structure?

**Statistic:** particle-cloud σ_x/σ_z(t) on arm B vs arm A (round control); primary σ_x/σ_z @ t=2400.

| Verdict | Condition (arm-B σ_x/σ_z @ t=2400) |
|---|---|
| **SUPPORTS** | B σ_x/σ_z rises from ≈1.00 toward ≥1 and into the doctrine band **[1.8, 3.2]**; AND arm A stays round (σ_x/σ_z ≤ 1.1) |
| **CONTRADICTS** | B σ_x/σ_z shows no rise toward oblate (≤ 1.0) or moves prolate (decreases below 1.0); OR arm A fails the roundness guard |
| **INCONCLUSIVE** | instability (non-finite) OR amplitude floor (arm-B peak density < 0.10 × peak0) |

σ_x/σ_y REPORTED for both arms (reference φ = 1.618, not a gate).

### Q2 (arm C) — does the particle-driven mass deform the two-fluid coherence bubble toward oblate?

**Statistic:** field-coherence σ_x/σ_z(t) (true physical) on arm C vs the wave-9 field baseline
(≈1.16, or 0.329 in the `sigma3` frame); and the particle-cloud σ_x/σ_z in the same run vs arm B.
Primary statistic: field σ_x/σ_z @ t=2400.

| Verdict | Condition (arm-C field σ_x/σ_z @ t=2400, true frame) |
|---|---|
| **SUPPORTS** | field σ_x/σ_z rises from ≈1.16 substantially toward ≥1.8 (the doctrine band); AND arm A is round |
| **CONTRADICTS** | field σ_x/σ_z shows no material rise (≤ 1.6) or decreases; OR arm A fails roundness |
| **INCONCLUSIVE** | instability / non-finite / amplitude floor |

The particle-cloud σ in arm C is REPORTED (vs arm B) to show whether the field's π/ρ modulation
changes the collapse anisotropically. If arm C proves too heavy at N=64 (> ~30 min wall), it is
**reported-not-gated** rather than skipped (the brief's option).

### Amended-rule clause

The references 2.510 / 1.618 are NOT gates. Any post-freeze change to any pin in §1 is FORBIDDEN; a
necessary change is disclosed as a **dated amendment** appended here and the affected arm re-frozen
before re-run. Neither decision trees nor numeric pins are weakened to make a gate pass.

**Amendment 2026-08-16 (a) — gradient sign convention (implementation, not a pin change):**
`triaxial3d_feed_probe.grad_phi` returns the BACKWARD difference `(φ[i−1]−φ[i+1])/(2h) = −∇Φ`
(its companion `div_vec` is also backward, so the two cancel inside wave-9's divergence-based Q2
source — that result is unaffected). The wave-10 particle force uses the gradient ALONE, so the
frozen physics `a = −G_N·∇Φ` (attractive) is implemented as `a = +G_N·grad_phi(...)`. The frozen
force convention is unchanged; only the implementation sign was corrected before the re-run.

**Amendment 2026-08-16 (b) — decision-tree precedence (the round control is ≈1.008, not exactly
1.000):** because the physically-round particle cloud measures σ_x/σ_z = 1.008 (sampling noise at
N_p = 32768), a "rise above 1.0" is not a material oblate signature. SUPPORTS therefore requires
entry into the doctrine band **σ_x/σ_z ≥ 1.8**; any value below that (stays ~round or prolate) is
CONTRADICTS. No numeric pin was weakened — this only removes the misleading ">1.0 = partial" bucket
and pins the SUPPORTS threshold to the frozen band.

## 3. Harness gates (verify_triaxial3d_particle.py → `ALL CHECKS PASSED`)

1. **G1 arm-A roundness:** free-streaming control σ_x/σ_z, σ_x/σ_y ∈ [0.95, 1.05] at all traces.
2. **G2 Poisson exactness:** single Fourier mode inversion rel err < 1e-9; k=0 null; Φ mean-zero.
3. **G3 TSC deposit:** total deposited mass == total particle mass (partition of unity); a single
   cell-center particle deposits mass 1.0 (Σ 27 weights = 1).
4. **G4 determinism:** arm B (100 steps) bitwise identical across two runs (particle positions).
5. **G5 no-NaN:** all arms finite at all traces.
6. **G6 REPORTED (not gated):** total-particle-mass drift across the run; KDK energy drift.

## 4. Stopping rule

Fixed: one physically-round seed (rng 42), N_p=32768, N=64, 2400 steps, three arms (A/B/C), one
analysis, deterministic. A CONTRADICTS is final for this wave. Only a new dated pre-registration
re-opens.

## 5. What does NOT count

- Post-hoc N, N_p, steps, dt, σ₀, G_N, rng-seed, π/ρ convention, g-factor, or arm changes.
- Reading σ-ratios as edge-steepness 1.70 (a different quantity).
- Claiming the numpy probe as the full Godot engine (no shader/engine/scene change here).
- Modifying `triaxial3d.py`, `triaxial3d_feed_*`, or any existing file.

## 6. Honest tiers

- **T1 measured** — particle σ ratios, density/conservation, determinism, Poisson exactness.
- **T2 inferred** — "the particle-nbody gravity does/does not produce oblate structure on the
  periodic (φ,1,φ²) box."
- **T3 out of scope** — the full engine (BH sector, dual-lattice/BCC, gradient order 4, RealSim
  dissipation, the full `g = 1+(φ⁶−1)q` chord factor, tree-meshless mode); any engine/scene/registry
  edit.

## 7. Number provenance

- Engine box, deposit, Poisson, river force, π/ρ clamp, G_N, gradient:
  `cassi_physics_engine.gd` (105, 908), `cassi_mass_deposit.glsl` (5-18, 100-198),
  `cassi_poisson.glsl` (9, 16-17, 147-158), `cassi_nbody_gravity.glsl` (12-13, 344-362, 499-532).
- Doctrine reference provenance: `oblate_provenance_audit.md` (§1, §3, §4), committed 27ad20f.
- Wave-9 field negatives: `triaxial3d_feed_report.md`.
- Wave-8 operator correction: `triaxial3d_simop_corr_report.md`.
