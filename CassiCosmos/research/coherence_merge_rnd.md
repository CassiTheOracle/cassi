# Coherence ∝ Structure? — The q-Growth Bug-vs-Physics Question & the Particle Merge Redesign

**Status:** R&D / measured-evidence + redesign proposal (merge/coherence workstream).
Read-only on every existing `.gd`/`.glsl` this turn — probe + doc are new files.
**Repo:** `godot/space-sim`. New: `scripts/verify_q_growth.gd`, `scenes/verify_q_growth.tscn`, this doc.
**Date:** 2026-08-14

---

## 0. Answer to the user's question (short version)

**The "coherence" that climbs past 1 is the sim's DISPLAY quantity `q_field = EY²+EI²`
— an UNBOUNDED field intensity, not a coherence. It is a real, growing thing, but it is
not what the framework calls coherence.** Measured over the two-fluid field of the engine
(this probe):

| arm | config | Σ(EY²+EI²) | peak q_field | ⟨q_coh⟩ | frac cells with q_coh>φ⁻² | corr(q_coh, ρ_mass) |
|-----|--------|-----------|--------------|---------|--------------------------|----------------------|
| **A** | src=0, 10 clusters, 600 st | 95.27 → **94.97** (flat) | 0.00047 → 0.00046 | 0.0018 | **0.000** | 0.0018 → 0.0077 |
| **A_long** | src=0, 10 cl, **6000 st** (t=12) | 95.13 → **95.08** (flat) | 0.00045 → 0.00051 | 0.0018 | 0.000 | → 0.0073 |
| **B** | **src=50** (strong pump), 600 st | 99.6 → **359.0 (×3.6)** | 0.0007 → **0.0177 (×27)** | 0.0019→0.0066 | 0.000 | → **0.053** |
| **C** | src=0, 1 cluster, 600 st | 95.27 → **94.97** (flat) | 0.00047 → 0.00046 | 0.0018 | 0.000 | → 0.013 |
| **D_meshless** | **live path** (Voronoi), src=0, 600 st | 95.02 → **95.83** (~flat) | 0.0004 → **0.0059 (×13)** | 0.0018 | 0.000 | → **0.402** |

**Conclusions:**

1. **The total field `Σ(EY²+EI²)` grows ONLY when pumped** (Arm B ×3.6 over 600 st when
   `source_strength=50`; flat/worse when `source_strength=0` in A/A_long/C — even over the
   long 6000-step horizon). The always-on `0.001·ρ` mass-density feedback in
   `cassi_two_fluid.glsl` is **numerically negligible** (`·dt² = 4e-6` attenuation) at the
   densities this config reaches — it does **not** pump the field. So the raw energy does
   not balloon by itself.
2. **Peak `q_field` concentrates even when the total is conserved** (Arm D ×13 in peak at
   ~constant total). This is the physical "coherence concentrates where structure forms"
   channel — the field redistributes into denser cores as matter clusters.
3. **`corr(q_coh, ρ_mass)` rises** with structure — most strongly on the **live meshless
   path** (Arm D → 0.40) — i.e. the framework's bounded coherence becomes spatially
   correlated with matter as structure forms. So in a coarse sense the user is right:
   **coherence does scale with structure via CONCENTRATION, not via total-energy growth.**
4. **BUT the amplitude is nowhere near "> 1"**: peak `q_field` stays ≤ 0.018 across all
   arms, and `⟨q_coh⟩` stays ~0.0018 with **zero cells crossing the merge gate φ⁻²**.
   The user's "climbs past 1" therefore cannot be the raw field — it is the **colour band
   re-anchoring**. The live band is `qi_cycle = (0.005, 1)`, `qi_approach = (0.8, 1)`, and
   the sim's Auto-Track / auto-align tracker (sim_ui.gd) *re-fits* the lo/hi handles to the
   live p2/p98 of the coherence distribution every ~1.5 s. As the field concentrates, the
   band's top handle is dragged *up past* the nominal `1.0` white point (the tracker is
   unbounded — it glides `qi_cycle.y` and `qi_approach.y` to follow the growing p98), so the
   display shows "coherence rising past 1" while the *row* quantity never exceeds ~0.02.
   **Verdict: the "climbs past 1" is a DISPLAY/anchor artifact of the unbounded colour
   scale, not a physical divergence.**

5. **The merge's gate `q_coh = ρ²/(ρ²+φ⁻²+ε²)` is flunked in BOTH directions at once**
   (the gate-selectivity problem, §3a): at the realistic amplitudes here `q_coh ≈ 0.002 ≪
   φ⁻²`, so **zero cells qualify** and the gate would never fire from the field's own state;
   while at high amplitude `q_coh → 1` for *any* field (order or not), so the gate can never
   tell "strong coherent structure" from "strong incoherent noise". The observed "merges to
   one particle" is therefore driven by the **distance-only** arm (`d ≤ R_m`, always active)
   once any seed coherence appears — the gate contributes almost nothing at low amplitude and
   is meaningless at high amplitude.

**Net:** the extreme "coherence" the user watches is a growing but bounded *concentration*
signal rendered through an auto-expanding *unbounded* colour band; it is **not** a
divergence bug, but it is also **not** the framework's coherence — the sim conflates three
different quantities under one name. The merge redesign (§3) replaces the amplitude-blind
gate, adds physical binding, and gives survivors structure.

---

## 1. Q-definition audit — every "q/coherence" quantity

The repo has **six** numerically distinct things all called "q/coherence". Three are
bounded, three are unbounded; only one matches the framework's definition doc.

| # | name (in code/docs) | formula | range | computed where | consumed where | misleading? |
|---|-------|---------|-------|----------------|----------------|-------------|
| 1 | **field q** `q_field` | `EY² + EI²` | **[0, ∞)** unbounded | `cassi_two_fluid.glsl` pass_b (`q[id] = ey²+ei²`, line 234), **comment says "q = (EY² + EI²) normalized"** | colour band / Qi-rainbow (`cassi_sim.gd` `qi_cycle`), instancer `tri_q` (color_mode≥2), q-histogram/auto-align, `_q_mean` telemetry (strided sum), field render, `cassi_condensation.glsl` BH nucleation (`qval > qi_threshold`) | **YES** — the `// normalized` comment is false; it is an unbounded intensity. **This is the user's "coherence".** |
| 2 | **merge gate** `q_coh` | `ρ²/(ρ²+φ⁻²+ε²)`, ρ=EY+EI, ε=EY−φ·EI | **[0,1)** | `cassi_particle_merge.glsl` `qcoh_at` (in-shader, trilinear at pair midpoint) | merge pass `pass_best` gate (`> q_threshold = φ⁻²`) | **YES** (gate-selectivity) — saturates →1 for ANY strong field (§3a) |
| 3 | **river-law q** | same form as #2 (`chord_g_from` in `cassi_nbody_gravity.glsl`) | [0,1) | nbody gravity arm, telemetry `q_min`/`q_max` at particles | gravity prefactor `g = 1+(ξ−1)·q` | No (matches #2's form; it IS the framework's field q) |
| 4 | **heuristic q_s** | `EY² + EI² + 0.01·ρ_mass` | [0,∞) | `cassi_nbody_gravity.glsl` legacy heuristic arm | heuristic gravity (mode 1) | **YES** — an ad-hoc "M2Q density hack – NOT the law" (shader's own comment) |
| 5 | **meshless q** | `ρ²/(ρ²+φ⁻²+ε²)` (Voronoi steering) | [0,1) | `cassi_voronoi_cells.glsl` (q at mode-4 steer) | Qi-gated Lloyd steering `κ_eff = κ·(1−q)^p` — **the framework's (1−q) conversion gate, present ONLY here** | No |
| 6 | **raster q** | `ey² + ei²` (Voronoi) | [0,∞) | `cassi_voronoi_raster.glsl` line 149 | same colour/telemetry as #1 | **YES** (same unbounded convention) |
| — | **framework 'coherence'** (cassi_definitions.md) | `qi = (EY−φ·EI)/(EY+φ·EI)` | **[−1,1]** | parent repo docs/`cassi_two_fluid_3d_gpu.py` | theory docs only; NOT the sim's display q | the sim does NOT use this bounded alignment at all |

**Critical absence (the bug-vs-physics crux):** the framework's full solver
(`two-fluid/cassi_two_fluid_3d_gpu.py`) has the **Qi-gated conversion**
`conv = −λ·(1−q)·(EY−φ·EI)` with `q = ρ²/(ρ²+φ⁻²+ε²)` (blocks conversion at high
coherence) **and a mass-conserving floor+renormalise**. The Godot **grid** two-fluid
(`cassi_two_fluid.glsl`) has **neither**: `pass_a` evolves a bare
`∂²ψ/∂t² = c²∇²ψ ∓ ω₀²·(EY−φ·EI)` with permanent Gaussian + `0.001·ρ` source terms, no
`(1−q)` gate, no floor/clamp, no dissipation. The `(1−q)` gate exists **only in the
meshless Voronoi arm** (#5), and even there only as *steering* (skips cells when q→1),
not as a mass conversion term. So the *live* sim's field is a different PDE from the
framework's — a genuine model-mismatch finding, not just a display quirk.

---

## 2. Growth measurement — method & numbers

**Probe:** `scripts/verify_q_growth.gd` (+ `scenes/verify_q_growth.tscn`), windowed console
exe, main-thread local RD, engine-instantiation pattern from `verify_merge_engine.gd`.
Config inherits the live `main.tscn` geometry (attractor field IC, `river_calibrate_gn`,
grid_N=64) at `N_particles=30000` for speed, `gravity_mode=3` (river-self, no dissipation —
clean physics). Reads raw `_field_ey/_field_ei/_field_vel/_mass_density_buf` on the same
thread after each `run_steps`. Full JSON → `_diag/q_growth_report.json`.

**Time series (selected rows; full series in the JSON):**

Arm A (source_strength=0, 10 clusters) — **no pump ⇒ no total growth**:
```
step  Σρ        Σ(EY²+EI²)  peak_q   mean_qc  >gate  corr(q,ρ)  H(kin+coup)
20    6863.88    95.268   0.00047  0.00180  0.000  0.0018   0.857
200   6863.92    95.126   0.00045  0.00180  0.000  0.0032   1.043
400   6863.95    94.967   0.00044  0.00179  0.000  0.0063   1.214
600   6863.99    94.974   0.00046  0.00179  0.000  0.0077   1.184
```

Arm A_long (source_strength=0, 6000 st, t=12) — **flat for 12 time units**:
`Σ(EY²+EI²)` 95.13 → 95.08 (±0.2% oscillation), peak_q ~0.0005 (±0.0001), corr→0.007.

Arm B (source_strength=50) — **pump ⇒ linear total growth + concentration**:
```
step  Σρ        Σ(EY²+EI²)  peak_q   mean_qc  >gate  corr(q,ρ)  H
20    7013.7     99.57     0.0007  0.00188  0.000  0.070    2.15
200   8362.1    152.09     0.0034  0.00287  0.000  0.116   48.28
400   9860.4    240.18     0.0090  0.00450  0.000  0.066    4.91
600  11358.7    359.01     0.0177  0.00663  0.000  0.053   44.22
```
Σ(EY²+EI²) grows at ~0.43/step (linear, not exponential); Σ(EY+EI) grows ~linearly
(+6.0/step). Peak_q concentrates ×27. H (kinetic+coupling energy) is *not* conserved under
pump (swings 2→48→4→44) — the source injects energy the coupling re-distributes.

Arm C (source_strength=0, 1 central cluster) — **no pump ⇒ no growth**, same flat pattern
as A. Removes the multi-ball-merger interaction; the density-contrast feedback alone does
not grow the field.

Arm D_meshless (source_strength=0, **live Voronoi path**) — **concentration WITHOUT total
growth**:
```
step  Σρ        Σ(EY²+EI²)  peak_q   mean_qc  >gate  corr(q,ρ)  H
20    6865.8     95.018   0.0004  0.00180  0.000  -0.001   0.19
200   6867.8     95.060   0.0005  0.00180  0.000   0.090   0.20
400   6878.1     95.379   0.0022  0.00180  0.000   0.381   0.21
600   6886.5     95.666   0.0059  0.00182  0.000   0.402   0.02
```
peak_q **×13** (0.0004 → 0.0059) at ~constant total; **corr(q_coh, ρ_mass) → 0.40** — the
meshless field genuinely concentrates its coherence where matter is, far stronger than the
grid path's 0.008.

### 2b/4. Energy conservation (item 2(b), item 4)

- **`Σ(EY²+EI²)` is conserved to ~0.2% at `source_strength=0`** (A/A_long/C flat). The
  bare wave system does NOT pump itself.
- **The scheme is the symplectic-Euler variant of leapfrog** (`v_new = v_old + a·dt` then
  `x_new = x_old + v_new·dt` in `pass_a`) — canonically symplectic and consequently
  *energy-stable (bounded oscillation, no secular drift)* for a source-free Hamiltonian.
  My measured kinetic+coupling energy `H = ½Σv² + ½ω₀²Σε²` oscillates in [0.77, 1.28]
  without secular growth over 6000 steps — consistent with a clean symplectic-Euler core.
  (The omitted `½c²|∇ψ|²` gradient term absorbs part of the oscillation — my H is a partial
  energy; the *conclusion that there is no secular growth when unpumped* is robust because
  `Σ(EY²+EI²)` itself is flat.)
- **Under pump the energy grows linearly** (Arm B) — the `+ source·dt²` term adds a
  constant per step once the pump is on. That is **expected** physics (external drive), not
  a hidden numerical blowup. **Finding:** there is no *spontaneous* (unpumped) energy bomb;
  the "coherence keeps rising" is the drive/display, not a conservation violation.
- **Caveat (reported):** the task's arm "source_strength default WITHOUT particle
  feedback" is **not config-toggleable** — the `0.001·ρ` feedback in `source_ey/source_ei`
  does not multiply `source_strength`; it is hardcoded. Its contribution is measured to be
  negligible at these densities (·dt² attenuation), so the A vs C contrast + the flat-long
  A_long (6000 steps) is the honest proxy, and the constraint is recorded.

---

## 3. Merge redesign (the R&D core)

> **IMPLEMENTED 2026-08-15** in `compute/cassi_particle_merge.glsl` + both
> drivers (`cassi_sim.gd`, `cassi_physics_engine.gd`). All four layered
> criteria are live behind three default-on flags (`merge_sel_gate`,
> `merge_subsonic`, `merge_virial`); the gravitational-binding criterion is
> always on (doctrine). **Correction to §3c:** the stopping inequality below
> is written in the design as `2K < |W|`; that form blocks cold clumps
> (2K = 0) from ever accreting, so the **implemented criterion is `2K ≥ |W|`**
> (a virialised / self-supporting object stops accepting infall).

### 3a. The gate-selectivity problem (proven)

Analytic (immediate from the form):
```
q_coh = ρ² / (ρ² + φ⁻² + ε²)   →   1   as ρ→∞,  for ANY ε.
```
Numeric confirmation (same formula, over the field values):
```
ordered attractor  (ρ=0.026, ε≈0):      q_coh = 0.0018   (≪ φ⁻² → gate closed)
ordered, strong    (ρ=5,    ε≈0):       q_coh = 0.985    (> φ⁻²)
DISORDERED, strong (ρ=5,    ε=4):       q_coh = 0.604    (> φ⁻²  ← fires on disorder!)
DISORDERED, strong (ρ=100,  ε=99):      q_coh = 0.505    (> φ⁻²  ← fires on disorder!)
```
At fixed amplitude the ordered/disordered ratio caps at ≈1.8 — **the gate cannot separate
"strong ordered" from "strong noisy" structure.** And in the *live* field (all probe arms)
`frac_above_gate = 0.000` — **zero cells reach φ⁻² at realistic amplitudes**, so the gate
contributes nothing at low amplitude either. The observed "everything merges to one" is
therefore driven by the always-on distance arm (`d ≤ R_m`), with the coherence gate inert
(too strict where the field is weak, meaningless where it is strong).

**Selectivity measure (rewards ORDER, not amplitude).** The framework defines coherence as
*alignment* to the φ-attractor and — via the coherence-budget doc — as the *organized,
low-mode* persistence of a structure. A gate must therefore be **scale-invariant and
order-rewarding**: it must pass a *smooth, phase-locked standing wave* and reject a
*loud, random* field regardless of amplitude. Doc-grounded choice:

```
q_sel = q_coh · q_ord
q_coh = ρ²/(ρ² + φ⁻² + ε²)                       # keep: the "condensed/coherent" barrier
q_ord = 1 / (1 + φ² · ⟪|∇(EY+φEI)|²⟫_local / (⟪(EY+φEI)²⟫_local + φ⁻²))
```
- `Σ = EY+φEI` is the coherent (φ-locked) combination; `∇Σ` its spatial gradient.
- `q_ord → 1` for a locally *smooth* field (small gradient vs field: a standing wave /
  condensate), `→ 0` for a rough/noisy field (large gradient).
- **Scale-invariant**: scaling both fields by λ multiplies `|∇Σ|²` and `Σ²` by λ², cancelling.
- **φ-anchored** (the `φ²` crossover at `|∇Σ|²/Σ² = φ⁻²`), parallel to the existing `φ⁻²`
  in `q_coh`.

**Honest tier (measured):** a 3×3 first-moment OR a 3×3 variance proxy does **not**
cleanly separate a loud-but-random field from a smooth standing wave at equal amplitude
(same 0.50–0.86 range — verified numerically). The sharp discriminator needs the
**spatial gradient / spectral** content: `q_ord` above (gradient-ratio form) or the
equivalent Fourier low-mode fraction — which is exactly the framework's *cascade*
organisation (structure = energy in the coherent low modes). Proposal is the gradient-ratio
form above; a falsifiable A/B test (below) gates it.

**The φ-anchor / why it's not another free knob:** the threshold remains `q_sel > φ⁻²`
(the framework's decoherence crossover, `PHI_INV2`, already the q-denominator scale and the
existing gate), and the only structural addition is the scale-invariant `∇Σ` normalisation
using the *same* φ. No new physics constant.

### 3b. The missing binding criterion (gravitationally bound pair + same flow)

**Gravitational binding (the primary new gate).** Replace/augment the coherence gate with
the actual bound-orbit condition, min-image `d`:
```
½ μ v_rel² < E_bind(d) ,   E_bind = G_eff m₁m₂ / d ,   μ = m₁m₂/(m₁+m₂),  v_rel = |vᵢ−vⱼ|
```
Grounding `G_eff` in the sim's actual gravity:
- The river calibration gives `G_eff ≈ 1.0` (`_gn_eff`, the calibrated effective river G)
  and `G_N ≈ 1.045` (`bh[1].w`) at this config — **use `G_eff = G_N·(1+ξ·q_mid)`**
  (qi-enhanced coupling, `ξ=φ⁶`; saturates at `(1+φ⁶)G_N ≈ 18.9·G_N` per
  `cassi_definitions.md` §3), with `q_mid` = `q_coh` at the pair midpoint from §3a. The
  binding test is then `½μv_rel² < G_N(1+ξ·q_mid)m₁m₂/d`.
- This is parameter-free (only G_N, ξ, q — all already in the engine). **Data needed:**
  reading `vᵢ,vⱼ` and `m₁,m₂` is already in the merge's buffers (§5); `d` is already
  computed in `pass_best`.

**Tangential / same-flow criterion (secondary).** Merging should also require the pair to
be approaching on a quasi-radial inflow, not a fast fly-by that happens to be within `R_m`.
Propose:
```
|v_t| < c_s ,   v_t = v_rel − (v_rel·d̂) d̂ ,   c_s = h₀/dt   (the grid wave speed)
```
`h₀ = 2·min(extent)/N_grid` is the reference cell (already how `R_m` is defined), and `dt`
the timestep — so `c_s = h₀/dt` is the two-fluid's phase speed (a wave crosses one cell per
step), the natural local "sound speed" of the field in code units. `|v_t| < c_s` means the
pair's transverse relative motion is subsonic. **Why:** structure (a condensate) forms where
the flow becomes subsonic / inflow-aligned; a supersonic transverse pair is a fly-by, not a
merger. This reads `vel` (already in the merge set) — no new machinery. State: this is the
**hypothesis-tier** criterion (the binding test in 3b is the primary; the tangential test
is a documented tightening with a falsifiable null).

### 3c. Angular momentum + object size + the stopping scale

**Angular momentum is currently discarded.** The SINK-hop transfers `mass`, `mom` (Σm·v),
`cen` (Σm·x) — but none of `pos × (m·v)` (orbital L of the pair). For a faithful,
non-fakery object the survivor must carry the accreted angular momentum (it becomes spin /
disk):
- Add a per-object spin accumulator `spin[]` (vec4: xyz = Σ_particles sᵢ, w = life), and in
  `pass_hop` transfer `ΔL = mᵢ · (posᵢ − pos_b) × vᵢ` into a merge-owned `spin_b` buffer
  (the persistent `alive/mass/mom/cen` family is the documented home — extend it with a
  spin slot; this is the **design doc**'s "per-object spin" per the task).
- The survivor keeps this `L`. At finalize, `L` can be exposed to the instancer/rendering
  and (doctrine) is exactly-conserved across the merge (the pair's orbital L becomes the
  object's spin).

**Survivor radius (Plummer-like, mass-tied).** Non-fakery objects must be *extended*, not
point masses. Use the repo's own mass→size law (`cassi_instancer.glsl` `SIZE_BY_MASS`):
```
R_obj = clamp( SIZE_K · m_obj^(1/3), SIZE_S_MIN, SIZE_S_MAX ),
      SIZE_K = 0.62, SIZE_S_MIN = 0.18, SIZE_S_MAX = 5.0     (world units)
```
(this is the instancer's documented size-by-mass rule; `main_plummer.tscn` uses the Plummer
softening `a = cluster_radius` as the resolution scale). The survivor's radius rides `pos.w`
(index/mass) so rendering/lensing already honor it. Optional Plummer softening: use
`a_obj = φ·R_obj` in the nbody force for the object (regularises the core; matches
`main_plummer`'s `gravity_mode=2` convention where `a = cluster_radius`).

**Stopping scale (when a merged object STOPS merging) — virial equilibrium.** A "real"
object stops accreting by collision when its self-gravity binds it into a relaxed,
virialised clump and further infall is resisted by internal pressure/spin. Concrete
criterion (doctrine-tier):
```
merge stops when  2·K_obj < |W_obj|   (virial ratio ~1/2),
K_obj = ½ m_obj |v_obj − v_flow|² + ½ L_obj²/(m_obj R_obj²),
W_obj = −G_eff m_obj² / (2 R_obj)
```
i.e. the merged object's internal kinetic (from its accreted spin + residual infall) is
comparable to its self-binding energy — a classical dissipative-collapse virialisation.
A survivor satisfying this is a **stable condensate bound by its own gravity**, and further
pairs against it merge only if the incoming pair's kinetic can overcome `|W_obj|`. This is
exactly the "object saturates" criterion the user wants — the sim stops collapsing to a
single point and instead forms resolved clumps. **Falsifiable:** a virialised survivor's
cluster of mergers must stop growing in a control run (no unbounded collapse to one).

### 3d. Honest tiering + falsifiable tests

| part | tier | grounded in | falsifiable test |
|------|------|-------------|------------------|
| Gate must be order/scale-invariant (not amplitude) | **Doctrine** | `cassi_definitions.md` (coherence = alignment/organisation); coherence-budget doc (structure = coherent standing wave) | A/B: smooth standing wave at ρ=5 passes; same-amplitude white-noise field must NOT pass `q_sel > φ⁻²` (currently both pass `q_coh`) |
| `q_ord = 1/(1+φ²·⟪∇Σ²⟫/(⟪Σ²⟫+φ⁻²))` specific form | **Hypothesis** | framework scale-invariance + φ-anchor | gate A/B above on synthetic ordered-vs-random; and live: `frac(Q_sel>φ⁻²)` rises only where structure is smooth |
| Gravitational-binding condition `½μv_rel²<G_eff m₁m₂/d` | **Doctrine** | `cassi_definitions.md` §3 (G_eff), engine calibration (G_N) | conserved-momentum merge where a bound pair merges but an equal-distance unbound pair (high v_rel) does NOT |
| Tangential/subsonic criterion `|v_t|<c_s` | **Hypothesis** | two-fluid wave speed; structure-forms-subsonic | bound-but-tangential pair (fly-by v_t>c_s, d<R_m) must NOT merge |
| Per-object spin conservation + extended radius | **Doctrine (principle) / Hypothesis (form)** | framework soliton doctrine; repo instancer size-by-mass | `ΣL` before = `ΣL` after across a merge; merged object radius = size-by-mass law; rendered object is extended, not a point |
| Virial stopping scale `2K<|W|` | **Hypothesis** | classical virial theorem | control: a virialised survivor's member-set stops growing (count saturates), unlike the current unbounded collapse-to-one |

---

## 4. Files added (commit with `git add -f`, staged explicitly)

- `scripts/verify_q_growth.gd` — the growth probe (3 arms + live-path arm + long horizon).
- `scenes/verify_q_growth.tscn` — probe scene.
- `research/coherence_merge_rnd.md` — this doc.
- `_diag/q_growth_report.json` — measured time series (gitignored; regenerated by probe).

**Repro (windowed console exe, NEVER --headless):**
```
"C:/Users/Carina/AppData/Local/Microsoft/WinGet/Packages/GodotEngine.GodotEngine_Microsoft.Winget.Source_8wekyb3d8bbwe/Godot_v4.7-stable_win64_console.exe" --path <space-sim> res://scenes/verify_q_growth.tscn
```
