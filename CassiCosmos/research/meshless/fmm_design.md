# FMM/Tree Gravity Kernel — Design & Prototype (Stage 5, MESHLESS_PLAN §10)

**Status:** Design + numpy prototype (`stage5_fmm.py`), gates G13/G14/G15 PASS
**Repo:** `godot/space-sim` (this file + `stage5_fmm.py` are the READ-ONLY wave's
two deliverables; the meshless shader arm is a parallel worker's file).
**Date:** 2026-08-13
**Companion:** `research/meshless/stage5_fmm.py` (the measured prototype).

This is the design for the last remaining MESHLESS_PLAN item — the "FMM/tree
gravity kernel" that replaces the periodic spectral Poisson
(`compute/cassi_poisson.glsl`) with **open-boundary tree-class far-field
gravity**, delivering the §0 promise: *"tree/FMM gravity permits open
boundaries, so the bubble fabric can form at its own phases, not multiples of
L/n."*

---

## 0. The chord doctrine (non-negotiable, carried unchanged)

The river force in `compute/cassi_nbody_gravity.glsl` (header + `chord_g_from`
+ `river_field_acc_smp`) is

```
q_coh = rho²/(rho² + phi⁻² + eps²),   rho = EY+EI,  eps = EY − phi·EI
g     = 1 + (phi⁶−1)·q_coh             (xi−1 = phi⁶−1, the chord coupling)
a     = −G_N·(pi/rho)·∇(g·Phi)         — the FULL chord gradient in ONE pass
       (∇(gΦ) = g∇Φ + Φ(ξ−1)∇q; never hand-split into separate terms)
```

With the explicit rule *"NEVER hand-split ∇(gΦ)"*. The tree carries
**CHORD-WEIGHTED sources**: each source contributes `m_s·g_s` with `g_s` from
the field at the source's cell, and the tree evaluates the *weighted* potential
and its gradient:

```
w_s          = m_s·g_s
Phi_g(r)     = Σ_s w_s / |r − r_s|            (monopole + quadrupole)
nabla Phi_g  = Σ_s w_s·(r − r_s)/|r − r_s|³
a_river      = −G_N·(pi/rho)_target · ∇Phi_g   (per-target prefactor kept)
```

The whole-product doctrine is preserved: `g` enters the **source weight** of a
single weighted potential `Phi_g`, whose multipole gradient is taken whole —
`∇(gΦ)` is never decomposed into `g∇Φ + Φ∇g` as separate acceleration terms.
The difference from the grid arm is where `g` lives (source-folding here vs
target-folding there); both are whole-product forms.

The prototype (`stage5_fmm.py`, `chord_weight_from_field`) computes `g` per
source from the two-fluid `(EY, EI)` exactly as the shader's `chord_g_from`
does, and the tree aggregates the `w_s = m_s·g_s`.

---

## Q1. Tree type — Barnes–Hut monopole/quadrupole walk vs full FMM

**Recommendation: a Barnes–Hut octree with monopole + quadrupole multipoles
(one-pass, no multipole-to-local two-pass). "FMM" here means tree-class
far-field gravity for the sim's scale, not the Greengard–Rokhlin two-pass.**

Justification, honest:

- **Scale.** The meshless arm has `ML_N1 = 16` → `2·16³ = 8192` mesh cells
  (`scripts/cassi_sim.gd` const block) plus up to ~50k particles. A per-frame
  gravity evaluation needs ~8k–58k sources and up to ~50k targets. At this
  scale a **single-pass BH walk** costs `O(N_targets · ⟨interactions⟩)` with
  ⟨interactions⟩ ≈ 100–250 per target (`stage5_fmm.py` timing: 240·N at 32k).
  That is ~5M–19M multipole interactions per frame — comfortably GPU-bound.

- **Full FMM (Greengard–Rokhlin)** adds a second (multipole→local) pass and
  translation operators that only pay off when the interaction count per target
  must drop to O(1). For ~8–58k sources the BH walk's ~100–250 interactions are
  already cheap, and the accuracy–cost lever (θ and quadrupole order) is simpler
  and more predictable than FMM translation engineering. The sim's *river* force
  is not the clean 1/r² Coulomb problem G–R was built for (the π/ρ prefactor and
  `g` vary per source/target), so the two-pass exactness buys little.

- **What the plan's "FMM" means.** MESHLESS_PLAN.md §2 says "tree/FMM gravity"
  and §10 lists "the FMM/tree gravity kernel" — the repo's own usage treats the
  two as one family. This design delivers the tree member (BH-style), which is
  the accurate-and-cheap one at this scale.

**Measured evidence (Q7/G13):** the prototype's quadrupole tree at θ=0.5 hits a
median relative force error of **7.5e-3** vs the direct O(N²) sum on 8192
points — better than monopole (1.4e-2) and under the 1e-2 target.

---

## Q2. GPU data structure, build, traversal, multipole order, θ

**Recommendation: a linear (flat-array) octree with pre-order sorting; build
via a per-cell atomic count/insert then a level-by-level octant radix sort;
traversal is one thread per target with an explicit interaction stack
(equivalently the wavefront the prototype walks); quadrupole order; θ = 0.5.**

- **Linear octree (Morton/pre-order), not pointer octree.** The prototype
  (`BHOctree`) stores nodes in flat arrays (center, half, weighted mass `W`,
  center-of-mass, packed trace-free quadrupole, child indices, contiguous
  particle range `[ps,pe)`). The GPU storage buffer holds these arrays directly;
  "children" are array indices, so traversal is cache-friendly and there is no
  pointer chasing. This is the standard GPU BH layout (GADGET-style).

- **Build algorithm.** A per-cell **atomic counter insert** (each source
  computes its top-level octant, `atomicAdd`s the bin count, writes its index)
  followed by **multi-pass octant radix sort** level by level — or, cheaper, a
  full 30-bit Morton code per source and a single radix sort (the sim already
  uses atomic scatter in `cassi_mass_deposit.glsl`, so the atomic-insert pattern
  is precedent). For 8k–58k sources the sort/build is a few ms on GPU. The
  prototype build (single-threaded numpy) is 0.3s at 8k / 1.25s at 32k —
  ~100× cheaper parallel on GPU, well under a frame.

- **Traversal.** One thread per target with an explicit **stack** (the
  `wavefront` in the prototype is exactly this: a frontier of (target, node)
  pairs processed level-by-level, each wave one vectorized batch). The stack
  version on GPU: each thread descends, pushing far-enough nodes to a per-thread
  LIFO, accepting them as multipoles. The prototype's measured walk is 100–240
  interactions per target; a GPU thread handling ~200 interactions is trivially
  within warp/lane budgets.

- **Multipole order: quadrupole.** Measured in G13 (Q7): quadrupole beats
  monopole at every θ (7.5e-3 vs 1.4e-2 median at θ=0.5; θ=0.7: 3.1e-2 vs
  4.7e-2). The cost of the quadrupole term is tiny (a 6-component packed tensor,
  two contractions per accepted node) — it is the same walk with ~3 extra
  ALU in the accept branch. Claim: "quadrupole nearly halves the median error
  for ~no extra walk cost." Justified.

- **Opening criterion (θ). θ = 0.5, size/distance > θ ⇒ open.** Standard BH:
  accept a node as a multipole when `cell_half_size / distance_to_COM ≤ θ`.
  Two hardening rules from the prototype (fmm correctness, not optional):
  1. **Always open a node whose bounding cube contains the target** (not just
     dist-to-COM): with θ approaching or exceeding 1/√3, a target near a cell
     corner can otherwise accept a node enclosing itself, contaminating the
     self-excluding force.
  2. **Leaves are always exact** (a 1-particle leaf is a point mass; self
     exclusion at the leaf that is the target's own source).
  θ=0.5 is chosen because it is the value, within the 0.5–0.7 band, at which the
  quadrupole tree clears the ≤1e-2 median force-error gate (7.5e-3). θ=0.6 gives
  1.7e-2 — above the gate; θ=0.5 is the documented operating point.

---

## Q3. Chord weighting on the mesh arm — where g_s comes from

**g_s = 1 + (ξ−1)·q_coh per SOURCE cell, from the mesh-cell field state
(EY, EI) at that cell.**

- In the meshless arm the gravity source is the cell fluid: each cell has the
  two-fluid state `(EY, EI)` (the `_ml_psi_y/_ml_psi_i` buffers), so
  `rho = EY+EI`, `eps = EY−φ·EI`, `q_coh = rho²/(rho²+φ⁻²+eps²)`, and
  `g = 1+(ξ−1)q_coh` are computed per cell from that cell's own values —
  identically to the shader's `chord_g_from` (the prototype's
  `chord_weight_from_field`).
- The force at a *target* then keeps the per-target `−G_N·(π/ρ)` prefactor,
  where `π/ρ` at the target is `clamp((EY−EI)/(EY+EI), 0, 0.72)` per the law.

**Ordering constraint (load-bearing, for the integration wave): field → g → tree
build each step.** Because `g_s` is a function of the *current* cell field, the
tree **cannot** be built before the field is updated. In `_step_dispatches` the
PDE (or meshless cell lap) runs at step 2.x, so the tree build+walk must sit
AFTER the field/PDE pass and BEFORE the nbody kick, in the slot the spectral
Poisson+gradient chain currently occupies (Q6). Every step: `field → compute
g_s per source → build tree on w_s=m_s·g_s → walk → −G_N(π/ρ)∇Φ_g`.

---

## Q4. Sources — mesh-cell masses (ρ·V) only (monopole per the plan)

**Recommendation: mesh-cell masses are the tree sources.**

- MESHLESS_PLAN.md §2: "monopole = ρ·V" — the cell fluid IS the mass
  distribution in the meshless vision (matter forms natively from cells,
  §0/§7/R3). The grid arm already uses the mass-density grid ρ_cell as its
  source (deposited from particles); the tree uses the equivalent cell monopoles
  `m_s = ρ_cell·V_cell`, chord-weighted by `g_s` (Q3).
- **Particles** are *not* separate tree sources in this design: the meshless arm
  deposits particle mass into ρ (through the existing mass deposit), so the
  particle population's gravity is already represented by the cell masses if the
  deposit runs before the tree build. Adding a second particle-sourced tree
  would double the gravity sources for no physical gain while the deposit is
  active. The plan's Stage-3 "matter formation" (cell collapses into a particle)
  is when a distinct matter-particle tree arm becomes worth adding — deferred.
- Downstream of the meshless vision (when the field IS the fluid and the cell
  laps drive gravity), the cell monopole is the natural, sole source.

---

## Q5. Open boundaries — no periodic images; the steering tension

**The tree is evaluated in real 3-space with NO periodic images**: no k=0
nulling, no wrap-around. The prototype's G14 proves the open Plummer field
(analytic monopole, spherically symmetric) to median field error 1.5e-2 and
potential error 3.7e-3 in the resolved range — the exact §0 promise.

**The tension, stated honestly:** the *mesh steering* in the meshless arm
(`steer_and_remap` in `stage2_moving3d.py`, `_mesh_rebuild` in `cassi_sim.gd`)
wraps sites `mod L` — steering is **periodic**. Gravity becomes **open**. These
are now inconsistent at the box edge: a cell steered out one face wraps to the
other (periodic), but the mass it carries gravitates without images (open).

**Interim (proposed): the mesh stays periodic for the FLUID, gravity is open.**
- The wave field `(EY, EI)` keeps its boundary condition (the sim's sponge
  layer, D2) — the fluid PDE is not global, only mass transport, so periodic
  steering of the *fluid* cells is harmless and keeps the wave solver intact.
- Gravity uses the tree in open space: a mass near the box edge attracts as if
  the box were the whole universe (only the real mass within the domain, no
  ghosts). The consequence is a **monopole-ish falloff at the domain edge**
  instead of the spectral Poisson's periodic images — the bubbles form at their
  own phases (the promise) rather than at multiples of L/n.
- **What happens to the sponge/D2 behavior:** the sponge (wall-proximity
  damping of π, `stage2_moving3d.py` `wall_weight`/G7) still governs the *wave*
  field's absorption at the walls — unchanged. But the *gravity* no longer sees
  the box as a torus, so a particle ejected toward a wall is no longer pulled
  back by its own periodic image; it escapes into the open field (the "open
  provenance" the promise wants). This is the intended behavior, and it changes
  the D2 story: a candidate boundary damping for the gravity sector (not the
  wave sector) is a future refinement, but for bubble-fabric formation the open
  field is the point.

---

## Q6. Integration plan (LATER waves — design only, not implemented here)

**Toggle: `meshless_gravity`, default false** (parallel to the existing
`meshless_mode`; a new `@export` on `cassi_sim.gd`). With it off, the battery
(`verify_river_isotropy.tscn` 36/36, pinned anchors) stays **bit-identical** —
the spectral chain is untouched when the toggle is false, exactly like
`dual_grid`/`gradient_order` being additive.

**Pass placement in `_step_dispatches` (cassi_sim.gd:2360–2619):**

| Current pass | With `meshless_gravity` ON |
|---|---|
| 0. Poisson clear (ρ=0, telemetry) | SKIPPED (no spectral solve; ρ still cleared if deposit runs) |
| 1. Mass deposit → ρ_cell | KEPT (particles → cell densities; the tree's cell monopoles need ρ; the ρ grid also feeds the PDE/render) |
| 1.5. Spectral Poisson FFT chain | SKIPPED (tree replaces it) |
| 2. Two-fluid PDE / meshless cell lap | KEPT (field → g_s; Q3 ordering) |
| BH integrate / condensation | UNCHANGED (BH point sources still contribute the σ-regularized sector) |
| 2.8. ∇(g·Φ) grid gradient pass | SKIPPED (the tree's walk produces ∇Φ_g directly; no grid gradient) |
| 2.85. Dual lattice chain | SKIPPED (no grid to dual; the tree is already isotropic — this retires the BCC average for the tree arm) |
| 2.9. Acc warm-up | KEPT (cache first-step acc, one tree walk) |
| 3. N-body pass | REPLACED force source: the river arm samples `−G_N·(π/ρ)·∇Φ_g` from the tree instead of the grid `∇(g·Φ)` |

**New passes (inserted after step 2 / before nbody):**
1. **Tree build** — gather per-source `(EY,EI)` → `q_coh,g` → `w_s=m_s·g_s`;
   Morton/octant sort + per-node monopole `W,com` + quadrupole `Q`.
2. **Tree walk (force)** — one thread per target (mesh-cell centers and/or
   particle positions) producing `∇Φ_g`; the nbody pass applies `−G_N(π/ρ)`.

**Buffer budgets** (storage buffers; current sim buffers are
`N_particles·16` B or `ncells·16` B; the tree adds):
- node arrays: `(≤8·N_src+16)` nodes × (3+1+1+3+6 floats + 8 ints) ≈
  `(8·N_src)·~112 B` — for 8192 cells ≈ 7.3 MB; for 50k particles ≈ 45 MB.
  (Reasonable vs the existing 2.5M-particle pos/vel/acc at 3·2.5M·16 = 120 MB.)
- source table: `N_src × (pos 3f + w 1f + g 1f + EY/EI 2f)`.
- A dedicated push-constant block for the tree (build+walk params): grid/extent,
  θ, eps2, source count, target count, G_N — the RDNA3 128 B cap precedent
  (`_instancer_pc_bytes`).
- No new telemetry buffer (reuse `_tel_buf` counters for π/ρ clamps; the tree
  walk has no per-invocation chord samples, so `tel[7]` semantics change for the
  tree arm — the UI clamp-fraction readout must be re-derived).

**Which batteries stay bit-identical:** `verify_river_isotropy.tscn` (36/36,
pinned anchors) and every `.tscn` that runs the default `meshless_gravity =
false`. The toggle is additive the way `dual_grid`/`gradient_order` are — no
default-path code changes, so the pinned battery cannot move. The new arm is
validated by a NEW verify scene (tree G13/G14/G15 analogues on the GPU) rather
than by changing the existing ones.

---

## Q7. Accuracy target — what the tree actually needs

**Target: median relative force error ≤ 1e-2 vs the direct O(N²) sum at θ=0.5
(quadrupole). 99th percentile ~5e-2. Justification:**

- The current grid arm (`cassi_poisson.glsl` + dual + O4) has its own near-field
  errors: the measured ring anisotropy never drops below ~1.13 at 2h / 1.03 at
  4h, and the *absolute* force is ~1.6× the naive 1/(4πr²) convention
  (CASCADE_GRID.md §2/§4). The tree does not need to beat a perfect field — it
  needs to be *smooth and isotropic* (no lattice bias, the §0 promise) and
  accurate in the *median* (the bubble-fabric phase statistics, not the
  worst-deep-core target).
- The **median** is the right scalar: the bubble/fabric forms from coherent
  long-range and near-field structure, where a 1e-2 median force error is below
  the attraction/coherence thresholds that pin the lattice phases. Deep-cluster
  core targets (a handful), where the symmetric force nearly cancels, show
  large *relative* spikes but small *absolute* error — they don't move the
  fabric phase. G13 reports both the median (gated) and the 99th percentile
  (≈5e-2, diagnostic).
- **Measured:** monopole θ=0.5 median 1.4e-2 (fails); **quadrupole θ=0.5
  median 7.5e-3 (passes)**; θ=0.6 quad 1.7e-2 (fails), θ=0.7 quad 3.1e-2.
  The 0.5–0.7 band's low end, θ=0.5 with quadrupole, is the documented
  operating point.

### Prototype gates (stage5_fmm.py — all PASS)

- **G13** — tree vs direct O(N²) on 8192 points (uniform + Plummer cluster):
  quadrupole **median 7.5e-3 ≤ 1e-2** (monopole 1.4e-2); 99th pct 4.98e-2;
  gate the quadrupole (the better). tree walk 0.74s vs direct 3.29s (single
  thread numpy).
- **G14** — open-boundary Plummer sphere vs analytic monopole potential/field
  (no periodic images): potential median 3.7e-3, field median 1.5e-2 ≤ 2e-2 in
  the resolved range. (Deep-core relative spikes are equal-mass grain shot-noise
  where the symmetric field cancels — median is the gate.)
- **G15** — truncated Plummer cluster integrated 12 crossing times under the
  tree (per-step rebuild): **energy drift 7.3% ≤ 10%**, rms radius constant
  (stays bound). Honest note: |dE/E0| tracks the tree force error (the tree's
  multipole potential isn't the gradient of the exact pair U, so E drifts
  ~5.5× the median force error; θ=0.3 → 7%, θ=0.5 → 67%). The sim's river force
  is non-conservative anyway, so this gate's purpose is "stays bound with
  bounded drift at an adequately accurate tree," not exact E conservation.
- **Timing** (build+walk wall time, single-thread numpy, θ=0.5): N=2048 →
  0.08+0.08s, N=8192 → 0.31+0.48s, N=32768 → 1.25+2.83s; interactions ~98·N →
  ~240·N. This is the GPU design evidence: ~19M interactions at 32k, trivially
  parallel over ~5M lanes on a 7900 XTX at a few ms — under a frame. The GPU
  arm will be ~100× faster than these numpy numbers (build 1.25s→~10ms).

---

## Deliverables in this wave (read-only on sim code)

- `research/meshless/fmm_design.md` (this file)
- `research/meshless/stage5_fmm.py` (numpy prototype, G13/G14/G15 + timing)
- optional addendum in `MESHLESS_PLAN.md` §10 (commit if added)

No `.glsl`/`.gd`/`.tscn` edited — the meshless shader arm is a parallel worker's
ownership.
