# Oblate Bubble Provenance Audit — σ_x/σ_y = 1.422 and σ_x/σ_z = 2.510

**Status:** READ-ONLY audit. No repo modified (this file is the only deliverable).
**Date:** 2026-08-15
**Scope:** `CassiCosmos/`, `CassiTheory/`. No engine runs, no simulation executed.

---

## 1. Provenance verdict for 1.422 / 2.510

**Verdict: (c) derived/measured by a standalone Python *numpy* PDE — NOT a live Godot engine measurement, and NOT part of the engine or the `CassiCosmos` sim at all. The transverse ratio is seeded, then partially re-measured; the axial ratio is a genuine (but single-run, seed-dependent-window) emergent field measurement.**

The source of the doctrine's "recorded" numbers is
`CassiTheory/visual-explainers/string_bubble_cascade.py` — a self-contained 3D damped-wave two-fluid PDE solved with numpy RK4 and rendered with matplotlib. It imports no Godot, instantiates no engine, and reads no engine state. It is a pure Python research script (category **b/c**, not **a**, not **d**).

The literals `1.422` and `2.510` do **NOT** appear anywhere in the file — the numbers are **computed at runtime** from the coherence-weighted RMS extents of the evolved field. The producing lines:

- `string_bubble_cascade.py:317-330` — `rms_extents()` computes RMS extents `(sx, sy, sz)` of the perturbation energy `(EY-E0)²+(EI-E0)²`.
- `string_bubble_cascade.py:333-349` — `coherence_extents()` weights the field by a Gaussian centered at the coherence ratio `r = EY/EI = φ` (`weight = exp(-(r - PHI)^2 / (2 * 0.08^2))`) — "the actual bubble shape" — and computes `(sx, sy, sz)`.
- `string_bubble_cascade.py:434` — `idx_bubble = np.argmin(np.abs(snapshot_steps - 15000))` (i.e. the spheroid reading is taken at the step nearest **15000**).
- `string_bubble_cascade.py:446-449` — the ratios:
  ```python
  asp_xy = coh_sx_t[idx_bubble] / max(coh_sy_t[idx_bubble], 1e-12)
  asp_xz = coh_sx_t[idx_bubble] / max(coh_sz_t[idx_bubble], 1e-12)
  spheroid_confirmed = abs(asp_xy - PHI) < 0.3
  ```
- `string_bubble_cascade.py:697-699` — printed as the "measurement":
  ```python
  print(f"    Aspect ratio σ_x/σ_y = {asp_xy:.3f} (target: φ={PHI:.3f})")
  print(f"    Aspect ratio σ_x/σ_z = {asp_xz:.3f} (target: φ²={PHI**2:.3f})")
  print(f"    Spheroid confirmed: {'YES' if spheroid_confirmed else 'NO'}")
  ```

### Critical caveat — part of the "measurement" is baked into the initial condition

The transverse anisotropy σ_x/σ_y = φ is **hard-coded into the Gaussian seed** before any dynamics run, so the returned σ_x/σ_y ≈ φ partly measures back a value that was already imprinted:

- `string_bubble_cascade.py:98-100`
  ```python
  sigma0_z = np.full(N, sigma_r)  # constant transverse width—finite at all z
  sigma_x_z = PHI * sigma0_z
  sigma_y_z = sigma0_z
  ```
- `string_bubble_cascade.py:138-139` — this σ ratio feeds the envelope the string packets are seeded with:
  ```python
  T_env_b = np.exp(-(Xb**2 / (2*sigma_x_3d**2 + 1e-12) +
                      Yb**2 / (2*sigma_y_3d**2 + 1e-12)))
  ```

So `σ_x/σ_y` is **not an emergent engine or PDE discovery** — it is φ by construction of the IC envelope. The coherence-weight that measures it (line 339) is also pinned at φ by construction, so the estimator reads back the same ratio that was seeded. The **σ_x/σ_z** ratio carries more weight: no φ anisotropy is seeded along z (the string is the z-axis; the anisotropy is only in the xy envelope), so 2.510 is an emergent runtime result — but it is a **single unseeded run** at a fixed grid/resolution, with no seed/ensemble averaging or error bar.

### Additional caveat — the "step ~1100" in the docs does not match the code

The docs repeatedly label the record as "step 1100" (see §2), but the code selects `idx_bubble = argmin(|snapshot_steps − 15000|)` (`:434`), and at the default `steps = 3500` (`:53`, `:65`) the nearest snapshot to 15000 is the **final step 3500**. The `15000` anchor is only reachable at a ~15 k-step run. The code's own label is "step nearest 15000"; the "1100" in the corpus is not reproduced by the code as written at default settings. Either the numbers came from a non-default high-step run, or a stale / mismatched step label. Either way the provenance path is the empirical numpy output, not a documented, reproducible script run.

**Bottom line:** `1.422` and `2.510` are single-run empirical outputs of the *Python* PDE `string_bubble_cascade.py`, not engine measurements. `σ_x/σ_y = 1.422` is heavily seeded-in (IC envelope ratio φ ≈ 1.618; the ±0.3 confirmation window `:449` admits it). `σ_x/σ_z = 2.510` is emergent for that run (no z-anisotropy seeded) but is not engine-measured, not averaged, and not reproduced by any documented invocation.

---

## 2. Search tabulation — every occurrence of these / related numbers

Patterns searched: `1.422`, `2.510`, `sigma_x`, `σ_x`, `sigma_y`, `σ_y`, `sigma_z`, `σ_z`, `oblate`, `prolate`, `ellipsoid`, `2.618`, `1.618` across text/code files in `CassiCosmos/` and `CassiTheory/` (excluding `.git/`, `.godot/`, `_diag/`, binaries).

### 2a. The exact numbers `1.422` / `2.510` (and `2.618` / `1.618`)

| File | Context | Analytic vs measured | Traces to live engine run? |
|---|---|---|---|
| `CassiTheory/visual-explainers/string_bubble_cascade.py:447-449,698` | Computes `asp_xy`, `asp_xz` from coherence extents; prints them | **Measured** (numpy PDE), σ_x/σ_y partially seeded-in | **No** — Python only |
| `CassiTheory/foundations/bubble-edge-geometry.md:11` | Quotes "σ_x/σ_z=2.510 vs φ²=2.618, σ_x/σ_y=1.422 vs φ=1.618 **at step 1100**" and labels it "φ-ellipsoid bubble confirmed" | Cites the Python figure/script | **No** |
| `CassiCosmos/research/helix_solver/triaxial3d_prereg.md:35,50-51,91` | A1/A2 table rows "→ φ = 1.618 | **1.422**", "→ φ² = 2.618 | **2.510**"; cites "recorded 2.510 → φ² in string_bubble_cascade.py", "step 1100". Notes σ_x/σ_z "has never been measured by a solver" | Reference lines for a probe, sourced to the Python script | **No** (explicitly: never measured by the triaxial solver) |
| `CassiCosmos/research/helix_solver/triaxial3d_relax_prereg.md:20-23,39,57` | "The sim's own record (string_bubble_cascade.py, step ~1100) gives σ_x/σ_y = 1.422, σ_x/σ_z = 2.510 — **below** doctrine's φ/φ²"; a RELAXES→sim-record decision threshold uses 1.422/2.510 (±15%) | Cites the Python record | **No** |
| `CassiCosmos/research/helix_solver/triaxial3d_relax_probe.py:41,70` | Prints "sim record (step~1100): 1.422, 2.510 (string_bubble_cascade.py)"; verdict gate `abs(rend_xy-1.422)<0.15*1.422` etc. | Cites the Python record as a target | **No** |
| `CassiCosmos/research/helix_solver/triaxial3d_relax_report.md:17-18,32-36,49-53,74` | A/B table columns list doctrine φ/φ² and "1.422"/"2.510" as the sim-record reference; states the trial operator over-drives axial ratio (5.5→4.44) and does **not** reach 2.510 | Cites the Python record | **No** |
| `CassiCosmos/research/helix_solver/triaxial3d_report.md:106,119-121,134-136` | Cites "string_bubble_cascade.py (σ 1.422, 2.510 record)"; "recorded 2.510/1.422 at sim step 1100"; later: doctrine's oblate record σ_x/σ_z=2.510 **comes from the source feed / cluster geometry / gravity sector, not the anisotropic Laplacian** | Cites the Python record; independently concludes it is NOT an operator-only property | **No** |
| `CassiCosmos/research/helix_solver/triaxial3d_simop_corr_prereg.md:39-44` | Decision table: "the sim's recorded 2.510 requires a mechanism beyond the operator"; anchors (φ, φ²) and "sim record (1.422, 2.510)" are reference lines only | Cites the Python record | **No** |
| `CassiCosmos/research/helix_solver/triaxial3d_simop_corr_probe.py:9,44-45,64-66` | "sim's recorded sigma_x/z=2.510 must come from a mechanism the operator alone lacks"; "does NOT produce the sim's recorded sigma_x/z=2.510" | Cites the Python record | **No** |
| `CassiCosmos/research/helix_solver/triaxial3d_simop_corr_report.md:10-11,28-31,53-55` | (b) BUBBLE op columns list "σ_x/σ_z=2.510" as the sim record vs the trial's 4.442; "the sim's recorded σ_x/σ_z = 2.510 cannot come from the operator/dynamics alone" | Cites the Python record; concludes operator alone gives the opposite (prolate) | **No** |
| `CassiCosmos/research/helix_solver/triaxial_prereg.md:90-91` | Cites "bubble-edge-geometry.md §2.1 (φ ratio, recorded 1.42), §2.3 (B field, recorded 2.51)"; "visual-explainers/string_bubble_cascade.py (σ_x/σ_z = 2.510 vs φ², σ_x/σ_y = 1.422 vs φ at step 1100)" | Cites the Python record | **No** |
| `CassiCosmos/compute/cassi_poisson.glsl` (via box-aspect 1.618/2.618 seen in engine config) | Poisson uses per-axis extents from the φ-aspect box | Analytic (φ-aspect box) | Engine config, not a σ measurement |

### 2b. Related σ / oblate / prolate / ellipsoid occurrences (not the exact numbers)

| File | Context | Analytic vs measured | Live engine? |
|---|---|---|---|
| `CassiCosmos/scripts/verify_phi_box.gd:16-39,547-548,560-566` | Ellipsoid **ring test** and O(k⁴) "ellipsoidal dispersion" of the φ-box Poisson stencil at physical radii around a delta; validates stencil vs analytic symbol | **Analytic/verification** | Verifies the engine stencil, not a bubble-shape readout |
| `CassiCosmos/compute/cassi_two_fluid.glsl:77-81` | Doc: "direction-dependent (∝ h_i⁴k_i⁴ …) … expected ellipsoidal dispersion on an anisotropic lattice" | Analytic document of stencil dispersion | Describes the engine stencil |
| `CassiCosmos/compute/cassi_mass_deposit.glsl:7` | Calls the TSC scattering kernel "the 'bubble-shaped' deposit" (support 1.5h per axis) | Method-naming only, not a shape measurement | Deposit kernel |
| `CassiTheory/visual-explainers/spiral_string.py:53-55,128-131` | Triaxial ellipsoid axes `AX, AY, AZ = PHI, 1.0, 1.0/PHI`; wireframe ellipsoid | **Geometric construction** | No |
| `CassiTheory/visual-explainers/fibonacci_bubble_spiral.py:6-14,47-62,103-117,147` | "triaxial ellipsoid with axes (φ, 1, 1/φ)"; Fibonacci points on ellipsoid | **Geometric construction** | No |
| `CassiTheory/visual-explainers/bubble_pole_pentagons.py:3-9,75-175` | Geodesics on triaxial φ-ellipsoid; pole caustics | **Geometric construction** | No |
| `CassiTheory/visual-explainers/bubble_edge_geometry.py:620` | "F · 3D EDGE SHAPE—oblate triaxial spheroid" | Visual/geometric | No |
| `CassiTheory/visual-explainers/fractal_zoom.py:416` | "pole (φ-ellipsoid apex)" annotation | Visual | No |
| `CassiTheory/foundations/bubble-edge-geometry.md:112` | "an oblate triaxial spheroid—extended in Yang, contracted in Yin, bounded along the string" | Doctrine prose | — |
| `CassiTheory/foundations/bubble-lattice-fabric.md:65` | "an oblate triaxial spheroid—extended in Yang, contracted in Yin, bounded along the string" | Doctrine prose | — |
| `CassiTheory/foundations/qi-as-spatial-spacing-signal.md:109-111` | "ellipsoidal clump smears power across shells" (why a ladder can hide) | Reasoned prose | — |
| `CassiTheory/foundations/spin-fibonacci-spiral.md:88-98,488-490` | Notes the Fibonacci spiral is a **geometric** (not PDE-verifiable) property; cites `fibonacci_bubble_spiral.py` | Explicitly geometric, not measured | No |

**Overall:** Every occurrence of `1.422` / `2.510`, `1.618`/`2.618` as bubble σ-ratios traces back to the single Python script `string_bubble_cascade.py`; **none traces back to a live Godot engine run**. The `triaxial3d_*` suite (the `helix_solver` probes) already identifies these as *reference lines* and independently concludes the engine operator alone does **not** produce the oblate 2.510 (it yields prolate), directing the search to the source feed / cluster geometry / gravity sector (see `triaxial3d_report.md:134-136`, `triaxial3d_simop_corr_report.md:53-55`).

---

## 3. Engine facts (`CassiCosmos/scripts/cassi_physics_engine.gd`, `cassi_sim.gd`, shaders)

### 3a. Mass-deposit / source semantics

**Mass deposit** is a per-step **TSC (triangular-shaped cloud) scatter** of *particle* masses into the 3D field grid — a 27-cell separable quadratic B-spline, exact partition of unity, bit-deterministic integer fixed-point accumulation:

- `CassiCosmos/compute/cassi_mass_deposit.glsl:5-11,33` — "TSC … scatter of per-particle masses into the field grid. Each particle spreads mass to 27 surrounding cells with the separable quadratic-spline (B-spline) weights — the 'bubble-shaped' deposit … support 1.5h per axis."
- `cassi_mass_deposit.glsl:100-108` — "Mode 0: TSC … deposit," `if mass <= 0.0 return` — it runs **every step** over the live particle buffer, so it is a **sustained per-step feed** driven by where the particles currently are, **not** a single blob deposit and **not** a periodic re-seed of the cluster IC. The cluster IC seeding is separate, CPU-side (`cassi_sim.gd:227-237` "Bounded Plummer / Gaussian ball / Uniform sphere … truncated to the safe radius").

**`source_strength`** (default **0 = off** at `cassi_sim.gd:63` "Extra field injection from the deposited mass (0 = off)"; engine default `cassi_physics_engine.gd:88` `source_strength: float = 0.0`): a **scalar multiplier** that scales how much of the deposited PIC mass additionally injects the two-fluid field. It is a *field-source strength knob*, **not** a re-seed/re-seeder and not a blob source:

- `cassi_sim.gd:63` — "`@export var source_strength: float = 0.0  # PIC mass deposit drives field (set >0 for extra injection)`"
- Passed verbatim into the two-fluid meshless PC vector: `cassi_sim.gd:3176` `hx, hy, hz, c2, ML_OM2, PHI, source_strength, …`, and into the nbody/two-fluid push constants (`cassi_sim.gd:4207`, `4225`). Engine reads it at `cassi_physics_engine.gd:415` `source_strength = float(cfg.get("source_strength", source_strength))`.

`cluster_radius` (default 50.0): **the IC scale radius** and the geometric unit. It does **not** deposit mass by itself; it sizes the initial cluster and — via `cluster_radius * 1.5` — the box extents:

- `cassi_sim.gd:55` — "`@export var cluster_radius: float = 50.0   # initial cluster size`"
- `cassi_sim.gd:247-261` / `cassi_physics_engine.gd:908-909` — `_extents()`: `Vector3(box_aspect.x, box_aspect.y, box_aspect.z) * (cluster_radius * 1.5) * maxf(box_scale, 1e-3)` "the single source of truth for the box geometry (bh[2].yzw header slots, the Poisson/mass-deposit/two-fluid push constants, IC truncation — all derive from this)."

### 3b. Gravity sector

**Poisson solve: spectral FFT**, hand-rolled Stockham radix-2 autosort per axis, `Φ̂ = −ρ̂/k²`, `k = 0` nulled (mean-of-Φ unphysical):

- `cassi_poisson.glsl:9,16-17` — "`Cassi Spectral Poisson Solver — ∇²Φ = ρ_mass, Φ̂ = −ρ̂/k², k = 0 nulled.`" "`Φ̂(k=0) = 0; Φ̂(k≠0) = −ρ̂/k²`"
- `cassi_poisson.glsl:147-158` — `k2_of_cell`: `kxw = TWO_PI*float(kx)/(2.0*extent_x)` … `return kxw*kxw + kyw*kyw + kzw*kzw` — **per-axis torus periods** `L_i = 2·extent_i` from the φ-aspect box.
- `cassi_poisson.glsl:253` — inverse pass scales by `1.0/float(N)`; after the passes "the REAL part of the buffer holds Φ".

**Φ → field coupling: ∇(g·Φ)**, built in a dedicated cell-centered gradient pass, with `g = 1 + (ξ−1)·q`, `ξ = φ⁶`, applied as

```
a = −G_N · (π/ρ) · ∇(g·Φ)
```

always kept as the **whole product** (never hand-split `g∇Φ + Φ∇g`):

- `cassi_nbody_gravity.glsl:12-13` — "`a = −G_N·(π/ρ)·∇(g·Φ) — the FULL chord gradient in ONE pass (∇(gΦ) = g∇Φ + Φ(ξ−1)∇q; never hand-split)`"
- `cassi_nbody_gravity.glsl:19-24` — "GRADIENT ESTIMATOR … ∇(g·Φ) is now built ONCE PER STEP on the grid — a dedicated pass (pass_mode == 1…) evaluates S = g·Φ at cell centers … and stores the central differences ∇S to _grad_buf"
- `cassi_nbody_gravity.glsl:344-362` — gradient pass source: `q = ρ²/(ρ² + φ⁻² + ε²)` with `ε = EY − φ·EI`, returns `(1.0 + (pc.xi - 1.0) * q) * ph[id].x` — "`g · Φ — whole product`".
- `cassi_nbody_gravity.glsl:526-532` — the river force: `chord_g_from(fs.ey, fs.ei, …)`; `float G_N = bh[1].w; vec3 gv = …(fs.gradS + fs.gradS2)…; return -G_N * pi_over_rho * gv;`
- `cassi_nbody_gravity.glsl:499-518` — `chord_g_from`: `pi_over_rho = (eyv - eiv) / rho_f` clamped to `[0, 0.72]`; `return 1.0 + (pc.xi - 1.0) * q;` (the g factor).
- Sign: the **negative** `−G_N·(π/ρ)·∇(g·Φ)` is the attractive force toward mass. Scale: dimensionless `G_N` (bh[1].w), `π/ρ ∈ [0, 0.72]`, `g = 1 + (φ⁶−1)·q`.

**Box aspect the engine uses: `(φ, 1, φ²) = (1.618, 1.0, 2.618)`** — `x` = Yang (extended), `y` = Yin, `z` = String/flow:

- `cassi_physics_engine.gd:105` — "`var box_aspect: Vector3 = Vector3(1.618, 1.0, 2.618)`"
- `cassi_sim.gd:257-261` — "Theory preset (φ, 1, φ²) maps x = Yang (extended), y = Yin (contracted), z = String/P∥ (flow) … `@export var box_aspect: Vector3 = Vector3(1.618, 1.0, 2.618)`"

**Important thematic fact** (ties to §2): the *oblate* bubble ratio σ_x/σ_z = 2.510 cited by the doctrine is the **σ of a field distribution**, which this engine does not measure; and the engine's own gravity/Poisson box is the (φ,1,φ²) **aspect box** whose anisotropic stencil produces a *prolate* (z-stretched) coherence shape per the `triaxial3d_simop_corr` probes — the opposite direction of the doctrine's oblate record. The doctrine's 2.510 is not an engine observable.

### 3c. Is the bubble shape ever MEASURED (σ / ellipsoid readout) in the engine?

**No.** The engine has **no σ / RMS-extent / ellipsoid-ratio readout**. Grepping the engine (`cassi_physics_engine.gd`), the sim (`cassi_sim.gd`), and the shaders for `sigma_x`/`σ_x`/`sigma_y`/`σ_y`/`sigma_z`/`σ_z`/ellipsoid-as-readout returns:

- `sigma_*` names in code are **not** present in the engine; the only `sigma`-like term is in the field-shape *documentation* context (`cassi_two_fluid.glsl:77-79` "ellipsoidal dispersion" of the lattice — analytic, not a measured bubble).
- The engine's per-axis geometry is only the **box half-extents** (`_extents()`, `bh[2].yzw`), the **cell sizes** `h_i = 2·extent_i/N`, and the stencil *weights* for the anisotropic box — all geometric/config, not a measurement of an emergent dense bubble's shape.
- The lone "bubble-shaped" language in the engine is the **mass-deposit kernel** name (`cassi_mass_deposit.glsl:7` "the 'bubble-shaped' deposit"), describing the TSC weighting support, not a measured shape.

The engine's public readbacks are telemetry counters and field samples — `readback_telemetry` (`q_min/max`, `pi_min/max`, saturation fractions, `q_mean`), `readback_snapshot` (pos/vel/field_q/pot) — **none** of which computes a σ ratio or an ellipsoid extent:
- `cassi_physics_engine.gd:697-735` — telemetry dict keys: `q_mean, q_min, q_max, pi_min, pi_max, pi_sat_hi_frac, pi_sat_lo_frac, rho_guard_hits, eps_mean, hubble, scale_factor, gn_eff`.
- `cassi_physics_engine.gd:665-686` — snapshot dict: `pos, vel, field_q, pot, t` ("Potential = the real part of the FFT workspace" — i.e. `Φ`, the Poisson solution, not a shape).

**Conclusion:** any σ / ellipsoid/oblate number in the research corpus is produced by **Python research scripts** (geometric constructions and numpy PDE probes), or is doctrine prose — the Godot engine measures **no** bubble aspect ratio. The only "shape" content the engine emits is the raw field (`Φ`, `g·Φ`) and per-axis geometry config, from which an external probe *could* in principle compute moments, but the engine and sim ship no such readout.

---

## 4. Summary of findings

1. **Doctrine numbers 1.422 / 2.510 are NOT hard-coded** and **NOT engine measurements**. They are runtime-computed ratios (coherence-weighted RMS extents) in the Python numpy PDE `CassiTheory/visual-explainers/string_bubble_cascade.py` (lines 446-449, 697-699), from a step the code labels "nearest 15000" (default run: final step 3500), while the corpus cites "step ~1100" — a mismatched label.
2. **σ_x/σ_y = 1.422 is heavily seeded-in**: the IC envelope sets `sigma_x = φ·sigma_y` (`:99-100`), and the coherence estimator is pinned at `r = φ` (`:339`), so the transverse "measurement" mostly reads back the seed. **σ_x/σ_z = 2.510** is an emergent single-unseeded-run result (no z-anisotropy in the IC), but with no ensemble/seed averaging.
3. **Engine facts for a mechanism probe**: mass deposit = per-step TSC particle scatter (sustained feed from live particle positions; `source_strength` default **0/off** is a scalar field-injection gain, not a re-seed); gravity = **spectral Stockham FFT Poisson** (`Φ̂ = −ρ̂/k²`, `k=0` nulled) coupled to the field via **cell-centered `∇(g·Φ)`** with `a = −G_N·(π/ρ)·∇(g·Φ)` (whole product, `g = 1+(φ⁶−1)q`, `π/ρ ∈ [0,0.72]`); the engine uses the **`(φ,1,φ²)` aspect box** (`= (1.618,1.0,2.618)`), anisotropic per-axis extents feeding `h_i = 2·extent_i/N`.
4. **The engine never measures a bubble/oblate shape.** No σ/extent/ellipsoid readout exists; only telemetry counters, `Φ`/`g·Φ` fields, and box geometry config. The `triaxial3d_simop_corr` probes already conclude the doctrine's oblate 2.510 is **not** produced by the engine's anisotropic Laplacian (which yields the *opposite*, prolate) and must come from the source feed / cluster geometry / gravity sector — a question this audit confirms is still open and untested.
